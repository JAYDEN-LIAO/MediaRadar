# backend/services/mcp_service/tools/pipeline_tools.py
"""
Pipeline 阶段 Tools 实现

Tool 列表（5个）：
- screener_posts: 文本初筛帖子
- vision_analyze: 视觉图片分析
- cluster_posts: 向量聚类帖子
- analyze_cluster: LangGraph 全链路分析（同步）
- analyze_cluster_stream: LangGraph 全链路分析（SSE流式）
- run_full_pipeline: 端到端完整分析管线
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import Field

from ..adapter.radar_adapter import RadarAdapter
from ..schemas.mcp_types import Sensitivity


# ============================================================
# Tool 实现
# ============================================================

def register_pipeline_tools(mcp):
    """注册 Pipeline 相关 Tools"""

    @mcp.tool(
        name="screener_posts",
        description="文本初筛帖子。对一批帖子进行 LLM 驱动的初筛，判断是否与监控关键词相关。无关帖子会被过滤掉。可自动触发视觉分析（图片存疑时）。适合在抓取到原始帖子后进行第一轮过滤。"
    )
    def screener_posts(
        posts: List[Dict[str, Any]] = Field(
            description="待筛选的帖子列表，每条包含 post_id/title/content/url/image_urls/platform",
            examples=[[{"post_id": "123", "title": "华为新品发布", "content": "..."}]]
        ),
        keywords: List[str] = Field(
            description="监控关键词列表",
            examples=[["华为", "苹果"]]
        ),
        keyword_levels: Dict[str, str] = Field(
            default=None,
            description="关键词对应的敏感度，aggressive/balanced/conservative",
            examples=[{"华为": "aggressive", "苹果": "balanced"}]
        )
    ) -> dict:
        """
        文本初筛帖子
        """
        if not posts:
            return {"success": True, "data": [], "message": "无帖子可筛选"}

        if not keywords:
            return {"success": False, "error": "keywords 不能为空", "data": None}

        result = RadarAdapter.screener_posts(
            posts=posts,
            keywords=keywords,
            keyword_levels=keyword_levels or {}
        )

        return {
            "success": True,
            "data": result,
            "message": f"筛选完成，通过 {len(result)}/{len(posts)} 条"
        }

    @mcp.tool(
        name="vision_analyze",
        description="视觉图片分析。调用 Qwen-VL-Max 对图片进行多模态分析，提取视觉证据（如文字识别、场景理解、异常检测）。当帖子图文存疑时使用。"
    )
    def vision_analyze(
        image_url: str = Field(
            description="图片 URL 或本地路径",
            examples=["https://example.com/image.jpg"]
        ),
        post_text: str = Field(
            default="",
            description="帖子正文（可选，用于结合图片做分析）",
            examples=["华为发布新手机..."]
        ),
        platform: str = Field(
            default="wb",
            description="平台标识",
            examples=["wb", "xhs"]
        )
    ) -> dict:
        """
        视觉图片分析
        """
        if not image_url:
            return {"success": False, "error": "image_url 不能为空", "data": None}

        result = RadarAdapter.vision_analyze(
            image_url=image_url,
            post_text=post_text,
            platform=platform
        )

        return {
            "success": True,
            "data": {
                "vision_text": result,
                "platform": platform,
                "image_url": image_url
            },
            "message": "视觉分析完成"
        }

    @mcp.tool(
        name="cluster_posts",
        description="向量聚类帖子。将一批帖子通过 BGE-M3 embedding + HDBSCAN 聚类，按语义相似度归并为话题簇。适合在 Screener 之后对相关帖子进行话题聚合。"
    )
    def cluster_posts(
        posts: List[Dict[str, Any]] = Field(
            description="待聚类的帖子列表",
            examples=[[{"post_id": "1", "title": "帖子A"}, {"post_id": "2", "title": "帖子B"}]]
        ),
        keyword: str = Field(
            description="监控关键词",
            examples=["华为"]
        )
    ) -> dict:
        """
        向量聚类帖子
        """
        if not posts:
            return {"success": True, "data": [], "message": "无帖子可聚类"}

        if not keyword:
            return {"success": False, "error": "keyword 不能为空", "data": None}

        result = RadarAdapter.cluster_posts(
            posts=posts,
            keyword=keyword
        )

        return {
            "success": True,
            "data": result,
            "message": f"聚类完成，共 {len(result)} 个话题簇"
        }

    @mcp.tool(
        name="analyze_cluster",
        description="LangGraph 全链路分析。对一个话题簇进行 DeepSeek(analyst) → Kimi(reviewer) → Kimi(director) 三节点分析，输出风险等级、核心问题、预警简报。适合在 Cluster 之后对每个话题进行深度分析。"
    )
    def analyze_cluster(
        posts: List[Dict[str, Any]] = Field(
            description="该话题簇下的帖子列表",
            examples=[[{"post_id": "1", "title": "华为被制裁", "content": "..."}]]
        ),
        keyword: str = Field(
            description="监控关键词",
            examples=["华为"]
        ),
        sensitivity: str = Field(
            default="balanced",
            description="分析敏感度：aggressive（激进）/ balanced（平衡）/ conservative（保守）",
            examples=["balanced"]
        )
    ) -> dict:
        """
        LangGraph 全链路分析（同步版本）
        """
        if not posts:
            return {"success": False, "error": "posts 不能为空", "data": None}

        if sensitivity not in Sensitivity.values():
            return {
                "success": False,
                "error": f"sensitivity 必须是 {Sensitivity.values()} 之一",
                "data": None
            }

        result = RadarAdapter.analyze_cluster(
            posts=posts,
            keyword=keyword,
            sensitivity=sensitivity
        )

        status_map = {
            "safe": "✅ 安全",
            "alert": "🚨 预警"
        }

        return {
            "success": True,
            "data": result,
            "message": f"分析完成：{status_map.get(result.get('status', ''), result.get('status', ''))} "
                       f"（风险等级: {result.get('risk_level', 1)}）"
        }

    @mcp.tool(
        name="analyze_cluster_stream",
        description="LangGraph 全链路分析（SSE流式版本）。与 analyze_cluster 相同，但通过 SSE 流式输出每个节点的进度（analyst → reviewer → director → final_result），适合长时间分析时实时展示。"
    )
    async def analyze_cluster_stream(
        posts: List[Dict[str, Any]] = Field(
            description="该话题簇下的帖子列表",
            examples=[[{"post_id": "1", "title": "华为被制裁", "content": "..."}]]
        ),
        keyword: str = Field(
            description="监控关键词",
            examples=["华为"]
        ),
        sensitivity: str = Field(
            default="balanced",
            description="分析敏感度",
            examples=["balanced"]
        )
    ):
        """
        LangGraph 全链路分析（SSE流式版本）
        返回 SSE 格式的流式事件字符串异步迭代器
        """
        async for event in RadarAdapter.analyze_cluster_stream_async(
            posts=posts,
            keyword=keyword,
            sensitivity=sensitivity
        ):
            yield event

    @mcp.tool(
        name="run_full_pipeline",
        description="端到端完整分析管线。输入一个关键词，自动执行：抓取原始帖子 → Screener 初筛 → Vision 补分 → 聚类 → LangGraph 分析 → 预警发送。全程自动，无需手动分步调用。"
    )
    def run_full_pipeline(
        keyword: str = Field(
            description="监控关键词",
            examples=["华为"]
        ),
        platform: Optional[str] = Field(
            default=None,
            description="指定平台，不填则使用系统配置的全平台",
            examples=["wb", "xhs"]
        ),
        sensitivity: str = Field(
            default="balanced",
            description="分析敏感度",
            examples=["balanced"]
        )
    ) -> dict:
        """
        端到端完整 Pipeline
        """
        if not keyword:
            return {"success": False, "error": "keyword 不能为空", "data": None}

        # 触发爬虫
        crawl_result = RadarAdapter.trigger_crawl(keyword=keyword)
        if not crawl_result.get("success") and crawl_result.get("is_running"):
            return {
                "success": False,
                "error": "雷达正在运行中，请稍后再试",
                "data": {"is_running": True}
            }

        return {
            "success": True,
            "message": f"全链路分析已启动（关键词: {keyword}，敏感度: {sensitivity}）",
            "data": {
                "keyword": keyword,
                "platform": platform,
                "sensitivity": sensitivity,
                "crawl_status": crawl_result
            }
        }

    return (screener_posts, vision_analyze, cluster_posts, analyze_cluster, analyze_cluster_stream, run_full_pipeline)
