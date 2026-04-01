# backend/services/radar_service/pipeline.py
"""
Radar Pipeline 调度器

将爬虫数据处理流程编排为五个可组合阶段：
  ① ScreenerStage   - 纯文本初筛（asyncio 并发，Semaphore 限流）
  ② VisionStage      - 视觉证据提取（条件触发，仅处理 needs_vision 分支）
  ③ ClusterStage     - 向量聚类
  ④ AnalysisSubGraph - LangGraph 分析子图（analyst → reviewer → director）
  ⑤ 预警 + 聚合写入

对外接口：
  RadarPipeline.run(posts, platform, keyword_levels) -> List[PipelineResult]
  返回结果格式与 run_analysis_pipeline() 完全兼容，可直接传入 save_ai_result()。
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import List, NamedTuple
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import logger
from .schemas import ScreenerResult
from .llm_gateway import call_llm
from .vision_agent import call_vision_llm
from .embed_cluster import cluster_related_posts, merge_similar_clusters
from .analysis_graph import analyze_and_report
from .prompt_templates import SCREENER_PROMPT
from .topic_aggregator import TopicAggregator


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
    topic_id: str = ""          # 话题唯一标识（MD5）
    evolution_timeline: dict = None  # 话题演化时间线
    sentiment: str = "Neutral"  # LLM 返回的情感


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
    generated_title: str = ""  # LLM生成的标准标题（用于后续聚类）


class ScreenerStageResult(NamedTuple):
    """
    ScreenerStage 第一遍文本初筛的返回结果。

    passed:       纯文本直接判定相关，直接进入下一阶段
    needs_vision: 文本存疑但有图片，需要 VisionStage 二次确认
    rejected:     无关且不需看图，Early Exit 直接丢弃
    """
    passed: List[ScreenedPost]
    needs_vision: List[ScreenedPost]
    rejected: List[dict]  # 仅记录 post_id 供日志使用


# ============================================================
# Stage 1: Screener
# ============================================================

class ScreenerStage:
    """
    文本初筛阶段（asyncio 并发）。

    对每条帖子并发调用 Screener LLM，判定是否相关。
    - is_relevant=False 且 needs_vision=False → 直接丢弃（Early Exit）
    - is_relevant=True  → 进入下一阶段
    - is_relevant=False 且 needs_vision=True → 交给 VisionStage 复判
    """

    # Screener 阶段并发上限（DeepSeek API 限流保护）
    SCREENER_CONCURRENCY = 10

    def __init__(self, keywords: List[str], keyword_levels: dict):
        self.keywords = keywords
        self.keyword_levels = keyword_levels
        self._screener_semaphore = asyncio.Semaphore(self.SCREENER_CONCURRENCY)

    def _build_prompt(self) -> str:
        kw_with_levels = "、".join([
            f"{k}(监控等级:{self.keyword_levels.get(k, 'balanced')})"
            for k in self.keywords
        ])
        return SCREENER_PROMPT.format(keyword=kw_with_levels)

    async def _screener_single(
        self,
        post: dict,
        screener_prompt: str,
    ) -> tuple[str, dict | ScreenedPost | None]:
        """
        单个帖子的 Screener 调用（在线程池中执行）。

        Returns:
            - ("rejected", {"post_id": ...})
            - ("passed", ScreenedPost(...))
            - ("needs_vision", ScreenedPost(...))
            - (None, None) if exception
        """
        async with self._screener_semaphore:
            post_id = post.get("post_id", "")
            image_urls = post.get("image_urls", [])
            has_image = bool(image_urls)
            text_content = post.get("content", "")

            image_hint = (
                "\n【系统提示】：该帖子附带了图片，如果文本存疑或需要证据，可申请看图。"
                if has_image else ""
            )
            text_to_analyze = f"标题: {post['title']}\n正文: {text_content[:800]}{image_hint}"

            try:
                res = await asyncio.to_thread(
                    call_llm,
                    screener_prompt, text_to_analyze,
                    response_format="json", engine="deepseek",
                    pydantic_model=ScreenerResult
                )
            except Exception as e:
                logger.error(f"⚠️ [Screener] LLM 调用失败 (ID:{post_id}): {e}")
                return (None, None)

            # 早退：无关且不需看图
            if not res.get("is_relevant") and not res.get("needs_vision"):
                logger.info(f"⏭️ [早退] 文本判定无关，跳过 (ID:{post_id})")
                return ("rejected", {"post_id": post_id})

            # 提取 LLM 生成的标准化标题（用于后续聚类）
            generated_title = res.get("generated_title", "") or ""

            # 纯文本直接判定相关
            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword") or ""
                if matched_kw not in self.keywords:
                    matched_kw = next(
                        (k for k in self.keywords
                         if k in (post.get("title", "") + text_content)),
                        self.keywords[0] if self.keywords else ""
                    )
                logger.info(f"✅ [通过] 捕获舆情: {generated_title or post.get('title', '')[:15]}...")
                return ("passed", ScreenedPost(
                    post=post,
                    matched_keyword=matched_kw,
                    vision_text="",
                    generated_title=generated_title
                ))

            # needs_vision=True：交给 VisionStage
            matched_kw = res.get("matched_keyword") or ""
            if matched_kw not in self.keywords:
                matched_kw = next(
                    (k for k in self.keywords
                     if k in (post.get("title", "") + text_content)),
                    self.keywords[0] if self.keywords else ""
                )
            logger.info(f"👀 [待视觉] 文本存疑需看图 (ID:{post_id})")
            return ("needs_vision", ScreenedPost(
                post=post,
                matched_keyword=matched_kw,
                vision_text="",
                generated_title=generated_title
            ))

    async def run(self, posts: List[dict]) -> ScreenerStageResult:
        """
        纯文本初筛（asyncio 并发执行）。

        返回三分支结果：
        - passed:      文本直接判定相关（可直接进入 Cluster）
        - needs_vision: 需要 VisionStage 二次确认
        - rejected:    Early Exit，无关且不需看图
        """
        if not posts:
            return ScreenerStageResult(passed=[], needs_vision=[], rejected=[])

        screener_prompt = self._build_prompt()

        # 并发所有帖子（信号量限制上限）
        tasks = [
            self._screener_single(post, screener_prompt)
            for post in posts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        passed: List[ScreenedPost] = []
        needs_vision: List[ScreenedPost] = []
        rejected: List[dict] = []

        for item in results:
            if isinstance(item, Exception):
                logger.error(f"⚠️ [Screener] 并发任务异常: {item}")
                continue
            tag, value = item
            if tag == "passed":
                passed.append(value)
            elif tag == "needs_vision":
                needs_vision.append(value)
            elif tag == "rejected":
                rejected.append(value)

        logger.info(
            f"[Screener] 完成：passed={len(passed)}, "
            f"needs_vision={len(needs_vision)}, rejected={len(rejected)}"
        )
        return ScreenerStageResult(passed=passed, needs_vision=needs_vision, rejected=rejected)


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

        # 先收集所有聚类结果 dicts（跨 keyword 一起合并）
        all_cluster_dicts: List[dict] = []

        for keyword, sposts in groups.items():
            # 将 generated_title 注入到 post 字典中（用于后续 embedding）
            posts = []
            for sp in sposts:
                p = dict(sp.post)  # 浅拷贝，避免修改原始数据
                p["generated_title"] = sp.generated_title
                posts.append(p)

            # 调用向量聚类
            cluster_dicts = cluster_related_posts(posts, keyword)

            for cd in cluster_dicts:
                cd["keyword"] = keyword  # 标记所属 keyword
                all_cluster_dicts.append(cd)

        original_count = len(all_cluster_dicts)

        # ── 后处理：同类话题合并（安全网）───────────────
        # 仅小规模时启用（帖子数 <= 10），避免大流量时引入不必要的 LLM 开销
        total_posts = len(screened_posts)
        if len(all_cluster_dicts) > 1 and total_posts <= 10:
            all_cluster_dicts = merge_similar_clusters(all_cluster_dicts)
            logger.info(f"[Cluster] 合并后共 {len(all_cluster_dicts)} 个话题簇")
        # ─────────────────────────────────────────────────

        # 转换为 Cluster 对象
        all_clusters: List[Cluster] = []
        for cd in all_cluster_dicts:
            pid_list = cd.get("post_ids", [])
            keyword = cd.get("keyword", "")
            # cluster_related_posts 返回的 dict 中已包含 posts（带 generated_title）
            cluster_posts = cd.get("posts", [])
            if not cluster_posts:
                continue
            all_clusters.append(Cluster(
                topic_name=cd.get("topic_name", cluster_posts[0].get("title", "")[:15]),
                post_ids=pid_list,
                posts=cluster_posts,
                keyword=keyword,
                sensitivity="balanced"
            ))

        logger.info(f"[Cluster] 共产生 {len(all_clusters)} 个话题簇（原始 {original_count} → 合并后 {len(all_clusters)}）")
        return all_clusters


# ============================================================
# Stage 2b: Vision（条件触发）
# ============================================================

class VisionStage:
    """
    视觉证据提取阶段。

    接收 ScreenerStage 标记为 needs_vision 的帖子，
    调用 Qwen-VL-Max 提取图片证据，
    融合图文后二次复判，最终决定是否进入 Cluster。

    仅处理 post 中包含 image_urls 的帖子。
    """

    def run(self, needs_vision_posts: List[ScreenedPost]) -> List[ScreenedPost]:
        if not needs_vision_posts:
            return []

        # 复用 ScreenerStage 的 prompt 构建逻辑（提取关键字和等级）
        # VisionStage 自身没有 keywords，需要由外部注入，
        # 但由于 needs_vision_posts 已有 matched_keyword，直接复用
        from .prompt_templates import SCREENER_PROMPT
        from .schemas import ScreenerResult

        passed: List[ScreenedPost] = []

        for sp in needs_vision_posts:
            post = sp.post
            post_id = post.get("post_id", "")
            image_urls = post.get("image_urls", [])
            text_content = post.get("content", "")
            platform = post.get("platform", "wb")

            # 兜底：无图片则跳过（理论上不会发生，needs_vision 本身就暗示有图）
            if not image_urls:
                logger.info(f"⚠️ [Vision] needs_vision 但无图片，跳过 (ID:{post_id})")
                continue

            # 调用视觉模型
            logger.info(f"📸 [Vision] 提取图片证据 (ID:{post_id})")
            vision_text = call_vision_llm(
                image_urls[0],
                text_content,
                platform=platform,
                post_id=post_id
            )

            if not vision_text:
                logger.info(f"⚠️ [Vision] 图片解析失败，跳过 (ID:{post_id})")
                continue

            # 视觉补充后二次复判
            fused_content = f"{text_content}\n【视觉补充】：{vision_text}"
            text_to_analyze = f"标题: {post['title']}\n正文: {fused_content[:800]}"

            # 复用 Screener 的 prompt（需要 keyword）
            kw_with_level = f"{sp.matched_keyword}(监控等级:balanced)"
            screener_prompt = SCREENER_PROMPT.format(keyword=kw_with_level)

            res = call_llm(
                screener_prompt, text_to_analyze,
                response_format="json", engine="deepseek", pydantic_model=ScreenerResult
            )

            if res.get("is_relevant"):
                matched_kw = res.get("matched_keyword") or sp.matched_keyword
                passed.append(ScreenedPost(
                    post=post,
                    matched_keyword=matched_kw,
                    vision_text=vision_text,
                    generated_title=sp.generated_title  # 保留 Screener 生成的标准化标题
                ))
                logger.info(f"✅ [Vision通过] 融合图文后捕获 (ID:{post_id})")
            else:
                logger.info(f"⏭️ [Vision排除] 视觉证据仍无关 (ID:{post_id})")

        return passed


# ============================================================
# Stage 3: Analysis SubGraph（封装 LangGraph）
# ============================================================

class AnalysisSubGraph:
    """
    分析子图。

    对每个 Cluster 调用 LangGraph 分析管线
    （analyst → reviewer → director），
    并在分析前后注入话题演化追踪能力。
    """

    def run(self, cluster: Cluster) -> tuple[Cluster, dict, dict]:
        # 聚合多帖内容
        combined_text = ""
        for p in cluster.posts:
            combined_text += f"【发帖】{p.get('title', '')} - {p.get('content', '')[:200]}\n"

        mock_post = {
            "title": f"聚合话题：{cluster.topic_name}",
            "content": combined_text[:2500]
        }

        # ── 话题演化追踪（RAG 增强）──────────────────────
        from .topic_tracker import (
            generate_cluster_summary,
            retrieve_similar_topics,
            build_evolution_timeline,
            index_or_update_topic,
            build_topic_id,
        )
        import threading

        evolution_timeline = {}
        cluster_summary = ""

        # 仅 balanced / aggressive 敏感度启用追踪（节省资源）
        if cluster.sensitivity in ("aggressive", "balanced"):
            try:
                # 1. 生成簇摘要
                cluster_summary = generate_cluster_summary(cluster.posts, cluster.keyword)

                # 2. RAG 检索相似历史话题
                similar_topics = retrieve_similar_topics(
                    keyword=cluster.keyword,
                    topic_name=cluster.topic_name,
                    cluster_summary=cluster_summary,
                    top_k=5,
                    score_threshold=0.75,
                )

                # 3. 构造演化时间线（即使无历史也返回结构，供 Analyst 判断）
                evolution_timeline = build_evolution_timeline(
                    current_topic={
                        "topic_name": cluster.topic_name,
                        "keyword": cluster.keyword,
                        "cluster_summary": cluster_summary,
                        "risk_level": None,  # 分析前未知
                    },
                    similar_topics=similar_topics,
                )

                logger.info(
                    f"📊 [TopicTracker] keyword={cluster.keyword}, "
                    f"topic={cluster.topic_name[:20]}..., "
                    f"is_new={evolution_timeline.get('is_new_topic')}, "
                    f"signal={evolution_timeline.get('evolution_signal')}"
                )

            except Exception as e:
                logger.warning(f"⚠️ [TopicTracker] 话题追踪初始化失败: {e}")
                evolution_timeline = {}

        # 4. 调用 LangGraph 分析（携带演化上下文）
        result = analyze_and_report(
            mock_post,
            keyword=cluster.keyword,
            sensitivity=cluster.sensitivity,
            evolution_timeline=evolution_timeline,
        )

        logger.info(
            f"[Analysis] 话题【{cluster.topic_name}】→ "
            f"status={result['status']}, risk={result['risk_level']}"
        )

        # 5. 分析完成后，异步写入话题演化记录（仅高危舆情）
        risk_level = result.get("risk_level", 1)
        if risk_level >= 3 and evolution_timeline:
            def _async_index():
                try:
                    topic_id = build_topic_id(cluster.keyword, cluster.topic_name)
                    index_or_update_topic(
                        topic_id=topic_id,
                        keyword=cluster.keyword,
                        topic_name=cluster.topic_name,
                        cluster_summary=cluster_summary,
                        risk_level=risk_level,
                        posts=cluster.posts,
                        core_issue=result.get("core_issue", ""),
                        report=result.get("report", ""),
                    )
                    logger.info(f"📊 [TopicTracker] topic_id={topic_id} 已写入/更新 Qdrant")
                except Exception as e:
                    logger.warning(f"⚠️ [TopicTracker] 异步索引失败: {e}")

            threading.Thread(target=_async_index, daemon=True).start()

        return cluster, result, evolution_timeline


# ============================================================
# 结果收集
# ============================================================

def build_results(
    cluster: Cluster,
    analysis_result: dict,
    platform: str,
    evolution_timeline: dict = None,
) -> List[PipelineResult]:
    """
    将 Cluster + AnalysisResult 展开为 List[PipelineResult]，
    每个 post 一条记录，与 save_ai_result() 格式完全兼容。
    """
    from .topic_tracker import build_topic_id

    topic_id = build_topic_id(cluster.keyword, cluster.topic_name)
    ev = evolution_timeline or {}

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
            topic_id=topic_id,
            evolution_timeline=ev,
            sentiment=analysis_result.get("sentiment", "Neutral"),
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
    # 并发限制：Kimi 组织级别 max org concurrency=3，
    # 为保险起见设为 2（留一个余量给其他可能并发的请求）
    concurrent_limit: int = 2


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
        self.vision = VisionStage()
        self.cluster = ClusterStage()
        self.analysis = AnalysisSubGraph()
        self.aggregator = TopicAggregator()
        # Semaphore 限制并发分析数量，避免触发 Kimi org 并发限制
        self._semaphore = asyncio.Semaphore(config.concurrent_limit)

    def _get_sensitivity(self, keyword: str) -> str:
        kl = self.config.keyword_levels
        if isinstance(kl, dict) and keyword in kl:
            return kl[keyword]
        return "balanced"

    async def _run_with_semaphore(self, cluster: Cluster):
        """用 Semaphore 包装的 analysis.run，每次最多 concurrent_limit 个并发"""
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.analysis.run, cluster)

    async def run(self, posts: List[dict]) -> List[PipelineResult]:
        """
        执行完整管线：
          Screener(asyncio并发) → Vision → Cluster → [asyncio 并行分析] → 结果收集
        超时控制：整个 Pipeline 整体有 timeout 上限（单 cluster LLM 分析最耗时）。
        """
        try:
            return await asyncio.wait_for(self._run_inner(posts), timeout=self.config.timeout)
        except asyncio.TimeoutError:
            logger.error(f"[Pipeline] Pipeline 超时（>{self.config.timeout}s），强制终止")
            return []

    async def _run_inner(self, posts: List[dict]) -> List[PipelineResult]:
        """Pipeline 内部实现，不含超时控制（由 run() 统一包装）。"""
        # Stage 1: Screener（asyncio 并发初筛）
        screener_result = await self.screener.run(posts)
        if not screener_result.passed and not screener_result.needs_vision:
            logger.info("[Pipeline] Screener 阶段无相关帖子，全量过滤")
            return []

        # Stage 2: Vision（条件触发，同步调用，因为 vision_llm 有自己的并发保护）
        vision_passed = self.vision.run(screener_result.needs_vision)

        # 合并：纯文本通过 + 视觉二次通过
        final_screened = screener_result.passed + vision_passed
        if not final_screened:
            logger.info("[Pipeline] Vision 阶段后无相关帖子，全量过滤")
            return []

        # Stage 3: Cluster
        clusters = self.cluster.run(final_screened)

        # 为每个 Cluster 注入 sensitivity（从 keyword_levels 查找）
        for c in clusters:
            c.sensitivity = self._get_sensitivity(c.keyword)

        if not clusters:
            logger.info("[Pipeline] Cluster 阶段无有效话题")
            return []

        # Stage 4: 并行分析（asyncio + Semaphore 限流，避免触发 Kimi 并发限制）
        tasks = [self._run_with_semaphore(c) for c in clusters]
        analysis_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # Stage 5: 收集结果 + 预警 + 话题演化追踪
        final_results: List[PipelineResult] = []
        cluster_results: List[tuple] = []  # (cluster, result) pairs for aggregator

        for item in analysis_outputs:
            if isinstance(item, Exception):
                logger.error(f"[Pipeline] 分析异常: {item}")
                continue
            cluster, result, evolution_timeline = item

            cluster_results.append((cluster, result))

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

            final_results.extend(
                build_results(cluster, result, self.config.platform, evolution_timeline)
            )

        # ── 话题聚合写入 SQLite ─────────────────────────
        if cluster_results:
            try:
                clusters_for_agg = [c for c, _ in cluster_results]
                results_for_agg = [r for _, r in cluster_results]
                self.aggregator.aggregate_clusters(clusters_for_agg, results_for_agg)
            except Exception as e:
                logger.warning(f"⚠️ [Pipeline] 话题聚合失败: {e}")
        # ─────────────────────────────────────────────────

        logger.info(f"[Pipeline] 完成，共产出 {len(final_results)} 条结果")
        return final_results
