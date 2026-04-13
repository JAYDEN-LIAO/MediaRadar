"""Pipeline 各 Stage 单元测试"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Mock 外部依赖
@pytest.fixture(autouse=True)
def mock_external_deps():
    with patch('services.radar_service.pipeline.call_llm') as mock_llm, \
         patch('services.radar_service.pipeline.call_vision_llm') as mock_vision, \
         patch('services.radar_service.embed_cluster.cluster_related_posts') as mock_cluster, \
         patch('services.radar_service.embed_cluster.merge_similar_clusters') as mock_merge:
        mock_llm.return_value = {"is_relevant": True, "generated_title": "测试"}
        mock_vision.return_value = "图片正常"
        mock_cluster.return_value = []
        mock_merge.return_value = []
        yield

class TestScreenerStage:
    """ScreenerStage 逻辑测试"""

    @pytest.mark.asyncio
    async def test_screener_early_exit_irrelevant(self):
        """无关帖子应该 Early Exit，不调用 LLM"""
        from services.radar_service.pipeline import ScreenerStage

        screener = ScreenerStage(
            keywords=["华为"],
            keyword_levels={"华为": "balanced"}
        )

        # 帖子内容完全不匹配关键词
        posts = [{
            "post_id": "1",
            "title": "今天天气真好",
            "content": "适合出去玩"
        }]

        with patch('services.radar_service.pipeline.call_llm') as mock_llm:
            result = await screener.run(posts)
            # 关键词不匹配，帖子在创建任务前就被过滤，不会调用 LLM
            mock_llm.assert_not_called()
            # rejected 是已创建任务但 LLM 判定无关的帖子，该 post 根本没创建任务
            assert result.passed == []
            assert result.needs_vision == []
            assert result.rejected == []

    @pytest.mark.asyncio
    async def test_screener_passed_when_relevant(self):
        """包含关键词的帖子应该通过"""
        from services.radar_service.pipeline import ScreenerStage

        screener = ScreenerStage(
            keywords=["华为"],
            keyword_levels={"华为": "balanced"}
        )

        posts = [{
            "post_id": "2",
            "title": "华为发布新手机",
            "content": "华为最新款手机配置曝光"
        }]

        with patch('services.radar_service.pipeline.call_llm') as mock_llm:
            mock_llm.return_value = MagicMock(
                success=True,
                data={
                    "is_relevant": True,
                    "generated_title": "华为新品发布",
                    "needs_vision": False
                }
            )
            result = await screener.run(posts)
            assert len(result.passed) == 1
            assert result.passed[0].matched_keyword == "华为"

class TestVisionStage:
    """VisionStage 并行测试"""

    @pytest.mark.asyncio
    async def test_vision_stage_parallel_execution(self):
        """VisionStage 应并行处理多个图片"""
        from services.radar_service.pipeline import VisionStage, ScreenedPost

        vision = VisionStage()
        posts = [
            ScreenedPost(
                post={"post_id": "1", "image_urls": ["http://img1.jpg"], "content": "内容1", "title": "标题1", "platform": "wb"},
                matched_keyword="华为"
            ),
            ScreenedPost(
                post={"post_id": "2", "image_urls": ["http://img2.jpg"], "content": "内容2", "title": "标题2", "platform": "wb"},
                matched_keyword="华为"
            ),
        ]

        with patch('services.radar_service.pipeline.call_vision_llm', new_callable=AsyncMock) as mock_vision, \
             patch('services.radar_service.pipeline.call_llm') as mock_llm:
            mock_vision.return_value = "图片正常"
            mock_llm.return_value = MagicMock(
                success=True,
                data={"is_relevant": True, "matched_keyword": "华为"}
            )

            results = await vision.run_async(posts)

            # 两个图片应该被并行处理
            assert mock_vision.call_count == 2
            assert len(results) == 2

    def test_vision_stage_empty_input(self):
        """空输入应返回空列表"""
        from services.radar_service.pipeline import VisionStage

        vision = VisionStage()
        results = asyncio.run(vision.run_async([]))
        assert results == []

class TestClusterStage:
    """ClusterStage 合并逻辑测试"""

    @pytest.mark.skip(reason="cluster_related_posts 依赖真实 embedding API，需要集成测试环境")
    def test_cluster_merge_ratio_trigger(self):
        """簇密度 ratio > 0.3 时应触发合并"""
        from services.radar_service.pipeline import ClusterStage, ScreenedPost

        # 5个簇 / 10个帖子 = 0.5 > 0.3，应该触发合并
        with patch('services.radar_service.embed_cluster.cluster_related_posts') as mock_cluster:
            # 模拟 5 个独立的簇
            mock_cluster.return_value = [
                {"topic_name": f"话题{i}", "post_ids": [f"p{i}"], "posts": [{"post_id": f"p{i}", "title": "t", "content": "c"}]}
                for i in range(5)
            ]

            cluster = ClusterStage()
            sposts = [
                ScreenedPost(post={"post_id": f"p{i}", "title": "t", "content": "c"}, matched_keyword="华为")
                for i in range(10)
            ]

            with patch('services.radar_service.embed_cluster.merge_similar_clusters') as mock_merge:
                mock_merge.return_value = mock_cluster.return_value
                result = cluster.run(sposts)
                # merge_similar_clusters 应该被调用（因为 5/10=0.5 > 0.3）
                mock_merge.assert_called_once()
