# backend/services/radar_service/pipeline.py
"""
Radar Pipeline 调度器

将爬虫数据处理流程编排为四个可组合阶段：
  ① ScreenerStage   - 文本初筛（可早退）
  ② VisionStage      - 视觉证据提取（条件触发）
  ③ ClusterStage     - 向量聚类（asyncio 并行）
  ④ AnalysisSubGraph - LangGraph 分析子图（analyst → reviewer → director）

对外接口：
  RadarPipeline.run(posts, platform, keyword_levels) -> List[PipelineResult]
  返回结果格式与 run_analysis_pipeline() 完全兼容，可直接传入 save_ai_result()。
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import List, TypedDict, Optional
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import logger
from .llm_pipeline import (
    ScreenerResult,
    call_llm,
    call_vision_llm,
    cluster_related_posts,
    analyze_and_report,
)
from .prompt_templates import SCREENER_PROMPT


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class PipelineResult:
    """单个帖子的最终分析结果（与 save_ai_result() 兼容）"""
    post_id: str
    platform: str
    keyword: str
    title: str
    content: str
    url: str
    risk_level: int
    core_issue: str
    report: str
    publish_time: str
    status: str = "safe"
    topic_name: str = ""
    cluster_index: int = -1


@dataclass
class Cluster:
    """聚类结果单元"""
    topic_name: str
    post_ids: List[str]
    posts: List[dict]
    keyword: str
    sensitivity: str = "balanced"


@dataclass
class ScreenedPost:
    """通过 Screener 的帖子"""
    post: dict
    matched_keyword: str
    vision_text: str = ""


# ============================================================
# Stage 1: Screener
# ============================================================

class ScreenerStage:
    """
    文本初筛阶段。

    对每条帖子调用 Screener LLM，判定是否相关。
    - is_relevant=False 且 needs_vision=False → 直接丢弃（Early Exit）
    - is_relevant=True  → 进入下一阶段
    - is_relevant=False 且 needs_vision=True → 调用 Vision 后复判
    """

    def __init__(self, keywords: List[str], keyword_levels: dict):
        self.keywords = keywords
        self.keyword_levels = keyword_levels

    def _build_prompt(self) -> str:
        kw_with_levels = "、".join([
            f"{k}(监控等级:{self.keyword_levels.get(k, 'balanced')})"
            for k in self.keywords
        ])
        return SCREENER_PROMPT.format(keyword=kw_with_levels)

    def run(self, posts: List[dict]) -> List[ScreenedPost]:
        if not posts:
            return []

        screener_prompt = self._build_prompt()
        screened: List[ScreenedPost] = []

        for post in posts:
            post_id = post.get("post_id", "")
            image_urls = post.get("image_urls", [])
            has_image = bool(image_urls)
            text_content = post.get("content", "")

            image_hint = (
                "\n【系统提示】：该帖子附带了图片，如果文本存疑或需要证据，可申请看图。"
                if has_image else ""
            )
            text_to_analyze = f"标题: {post['title']}\n正文: {text_content[:800]}{image_hint}"

            # 第一道关卡：纯文本初筛
            res = call_llm(
                screener_prompt, text_to_analyze,
                response_format="json", engine="deepseek", pydantic_model=ScreenerResult
            )

            # 早退：无关且不需看图
            if not res.get("is_relevant") and not res.get("needs_vision"):
                logger.info(f"⏭️ [早退] 文本判定无关，跳过 (ID:{post_id})")
                continue

            # 需要看图，调用 Vision Agent
            vision_text = ""
            if res.get("needs_vision") and has_image:
                logger.info(f"📸 [Vision] Screener 申请看图 (ID:{post_id})")
                vision_text = call_vision_llm(
                    image_urls[0], text_content,
                    platform=post.get("platform", "wb"),
                    post_id=post_id
                )
                if vision_text:
                    # 视觉补充后复判
                    fused_content = f"{text_content}\n【视觉补充】：{vision_text}"
                    text_to_analyze2 = f"标题: {post['title']}\n正文: {fused_content[:800]}"
                    res = call_llm(
                        screener_prompt, text_to_analyze2,
                        response_format="json", engine="deepseek", pydantic_model=ScreenerResult
                    )

            # 二次判断后仍然相关
            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword") or ""
                if matched_kw not in self.keywords:
                    matched_kw = next(
                        (k for k in self.keywords if k in (post.get("title", "") + text_content)),
                        self.keywords[0] if self.keywords else ""
                    )
                screened.append(ScreenedPost(
                    post=post,
                    matched_keyword=matched_kw,
                    vision_text=vision_text
                ))
                logger.info(f"✅ [通过] 捕获舆情: {post.get('title', '')[:15]}...")

        return screened


# ============================================================
# Stage 2: Cluster
# ============================================================

class ClusterStage:
    """
    聚类阶段。

    将 Screener 输出的帖子按 keyword 分组，
    每组内调用 cluster_related_posts() 产生话题簇。
    sensitivity 由 RadarPipeline 在调用后填入。
    """

    def run(self, screened_posts: List[ScreenedPost]) -> List[Cluster]:
        if not screened_posts:
            return []

        # 按 keyword 分组
        groups: dict[str, List[ScreenedPost]] = {}
        for sp in screened_posts:
            groups.setdefault(sp.matched_keyword, []).append(sp)

        all_clusters: List[Cluster] = []

        for keyword, sposts in groups.items():
            posts = [sp.post for sp in sposts]

            # 调用向量聚类
            cluster_dicts = cluster_related_posts(posts, keyword)

            for cd in cluster_dicts:
                pid_list = cd.get("post_ids", [])
                cluster_posts = [p for p in posts if p.get("post_id") in pid_list]
                if not cluster_posts:
                    continue
                all_clusters.append(Cluster(
                    topic_name=cd.get("topic_name", posts[0].get("title", "")[:15]),
                    post_ids=pid_list,
                    posts=cluster_posts,
                    keyword=keyword,
                    sensitivity="balanced"  # 临时默认值，由 RadarPipeline 覆盖
                ))

        logger.info(f"[Cluster] 共产生 {len(all_clusters)} 个话题簇")
        return all_clusters


# ============================================================
# Stage 3: Analysis SubGraph（封装 LangGraph）
# ============================================================

class AnalysisSubGraph:
    """
    分析子图。

    对每个 Cluster 调用 LangGraph 分析管线
    （analyst → reviewer → director），
    """

    def run(self, cluster: Cluster) -> tuple[Cluster, dict]:
        # 聚合多帖内容
        combined_text = ""
        for p in cluster.posts:
            combined_text += f"【发帖】{p.get('title', '')} - {p.get('content', '')[:200]}\n"

        mock_post = {
            "title": f"聚合话题：{cluster.topic_name}",
            "content": combined_text[:2500]
        }

        result = analyze_and_report(
            mock_post,
            keyword=cluster.keyword,
            sensitivity=cluster.sensitivity
        )

        logger.info(
            f"[Analysis] 话题【{cluster.topic_name}】→ "
            f"status={result['status']}, risk={result['risk_level']}"
        )
        return cluster, result


# ============================================================
# 结果收集
# ============================================================

def build_results(
    cluster: Cluster,
    analysis_result: dict,
    platform: str
) -> List[PipelineResult]:
    """
    将 Cluster + AnalysisResult 展开为 List[PipelineResult]，
    每个 post 一条记录，与 save_ai_result() 格式完全兼容。
    """
    results = []
    for pid in cluster.post_ids:
        post = next((p for p in cluster.posts if p.get("post_id") == pid), None)
        if not post:
            continue
        results.append(PipelineResult(
            post_id=pid,
            platform=platform,
            keyword=cluster.keyword,
            title=post.get("title", ""),
            content=post.get("content", ""),
            url=post.get("url", ""),
            risk_level=analysis_result["risk_level"],
            core_issue=analysis_result["core_issue"],
            report=analysis_result["report"],
            publish_time=post.get("publish_time", "未知时间"),
            status=analysis_result["status"],
            topic_name=cluster.topic_name,
        ))
    return results


# ============================================================
# PipelineConfig & 总入口
# ============================================================

@dataclass
class PipelineConfig:
    keywords: List[str]
    keyword_levels: dict        # {keyword: sensitivity}
    platform: str
    alert_negative: bool = True
    timeout: int = 300         # Pipeline 单次运行超时（秒）


class RadarPipeline:
    """
    舆情雷达 Pipeline 总调度器。

    使用方式：
        config = PipelineConfig(
            keywords=["华为"],
            keyword_levels={"华为": "balanced"},
            platform="wb"
        )
        pipeline = RadarPipeline(config)
        results = await pipeline.run(raw_posts)

    返回值可直接传入 save_ai_result()。
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.screener = ScreenerStage(config.keywords, config.keyword_levels)
        self.cluster = ClusterStage()
        self.analysis = AnalysisSubGraph()

    def _get_sensitivity(self, keyword: str) -> str:
        kl = self.config.keyword_levels
        if isinstance(kl, dict) and keyword in kl:
            return kl[keyword]
        return "balanced"

    async def run(self, posts: List[dict]) -> List[PipelineResult]:
        """
        执行完整管线：
          Screener → Cluster → [asyncio 并行分析] → 结果收集
        超时控制：整个 Pipeline 整体有 timeout 上限（单 cluster LLM 分析最耗时）。
        """
        try:
            return await asyncio.wait_for(self._run_inner(posts), timeout=self.config.timeout)
        except asyncio.TimeoutError:
            logger.error(f"[Pipeline] Pipeline 超时（>{self.config.timeout}s），强制终止")
            return []

    async def _run_inner(self, posts: List[dict]) -> List[PipelineResult]:
        """Pipeline 内部实现，不含超时控制（由 run() 统一包装）。"""
        # Stage 1: Screener（同步调用，无 asyncio）
        screened = self.screener.run(posts)
        if not screened:
            logger.info("[Pipeline] Screener 阶段无相关帖子，全量过滤")
            return []

        # Stage 2: Cluster
        clusters = self.cluster.run(screened)

        # 为每个 Cluster 注入 sensitivity（从 keyword_levels 查找）
        for c in clusters:
            c.sensitivity = self._get_sensitivity(c.keyword)

        if not clusters:
            logger.info("[Pipeline] Cluster 阶段无有效话题")
            return []

        # Stage 3: 并行分析（asyncio + ThreadPoolExecutor 避免阻塞）
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.analysis.run, c)
            for c in clusters
        ]
        analysis_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # Stage 4: 收集结果 + 预警
        final_results: List[PipelineResult] = []
        for item in analysis_outputs:
            if isinstance(item, Exception):
                logger.error(f"[Pipeline] 分析异常: {item}")
                continue
            cluster, result = item

            # 高危预警
            if result["status"] == "alert" and self.config.alert_negative:
                from .notifier import send_alert
                urls = [p.get("url", "") for p in cluster.posts if p.get("url")]
                send_alert(
                    keyword=cluster.keyword,
                    platform=self.config.platform,
                    risk_level=result["risk_level"],
                    core_issue=cluster.topic_name,
                    report=result["report"],
                    urls=urls
                )

            final_results.extend(build_results(cluster, result, self.config.platform))

        logger.info(f"[Pipeline] 完成，共产出 {len(final_results)} 条结果")
        return final_results
