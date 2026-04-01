# backend/services/radar_service/topic_aggregator.py
"""
话题聚合器（Task 2）

将 Pipeline 输出的 Cluster 数据聚合为话题摘要，
写入 SQLite topic_summary + topic_posts 表，
供前端 /api/topic_list 和 /api/topic/{id} 调用。

主要职责：
  - aggregate_clusters()    - 聚合一批 Cluster
  - _aggregate_single()      - 聚合单个 Cluster 到话题
  - _calculate_risk_class() - risk_level → risk_class 映射
"""

from __future__ import annotations

import os
import sys
from typing import List, TYPE_CHECKING

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import logger
from .db_manager import (
    create_or_update_topic_summary,
    add_post_to_topic,
)

if TYPE_CHECKING:
    from .pipeline import Cluster


class TopicAggregator:
    """
    话题聚合器。

    使用方式：
        aggregator = TopicAggregator()
        aggregator.aggregate_clusters(clusters, platform)

    每个 Cluster 分析完成后调用，
    将 Cluster 写入 SQLite topic_summary + topic_posts 表。
    """

    def __init__(self):
        pass

    def aggregate_clusters(self, clusters: List[Cluster], analysis_results: List[dict]):
        """
        聚合一批 Cluster。

        参数：
            clusters: Pipeline 输出的 List[Cluster]
            analysis_results: 与 clusters 一一对应的分析结果列表
                              每个元素为 { "risk_level": int, "risk_class": str,
                                          "core_issue": str, "report": str }
        """
        if not clusters:
            return

        for cluster, result in zip(clusters, analysis_results):
            try:
                self._aggregate_single(cluster, result)
            except Exception as e:
                logger.warning(f"⚠️ [TopicAggregator] 聚合失败 topic={cluster.topic_name}: {e}")

    def _aggregate_single(self, cluster: Cluster, analysis_result: dict):
        """
        将单个 Cluster 聚合为一个话题记录。
        """
        from .topic_tracker import build_topic_id

        topic_id = build_topic_id(cluster.keyword, cluster.topic_name)

        risk_level = analysis_result.get("risk_level", 2)

        # ── sentiment：优先取 LLM 返回值，避免 reviewer 驳回后被错误映射 ──
        # analyst_result 中有 sentiment，safe 分支的 sentiment 被标准化为 "Neutral"
        llm_sentiment = analysis_result.get("sentiment", "").lower() if analysis_result.get("sentiment") else ""
        if llm_sentiment in ("negative", "positive", "neutral"):
            sentiment_map = {"negative": "negative", "positive": "positive", "neutral": "neutral"}
            risk_class = sentiment_map[llm_sentiment]
        else:
            risk_class = self._calculate_risk_class(risk_level)

        # ── core_issue：取 LLM 原始值，safe 分支会用误导性兜底值，过滤它 ──
        raw_core_issue = analysis_result.get("core_issue", "")
        _bad_phrases = ("无", "无明显风险", "被降级的普通问题", "舆情安全，无需生成报告")
        if raw_core_issue and raw_core_issue not in _bad_phrases and len(raw_core_issue) > 1:
            core_issue = raw_core_issue
        else:
            core_issue = ""

        report = analysis_result.get("report", "") or ""

        # 话题摘要
        cluster_summary = analysis_result.get("cluster_summary", "")

        # 平台列表
        platforms = list({p.get("platform", cluster.keyword) for p in cluster.posts})
        plat_name_map = {
            "wb": "微博", "xhs": "小红书", "bili": "B站",
            "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
        }
        platforms_cn = [plat_name_map.get(p, p) for p in platforms]

        # 写入 / 更新 topic_summary
        is_new = create_or_update_topic_summary(
            topic_id=topic_id,
            keyword=cluster.keyword,
            topic_name=cluster.topic_name,
            cluster_summary=cluster_summary,
            risk_level=risk_level,
            risk_class=risk_class,
            core_issue=core_issue,
            report=report,
            platforms=platforms_cn,
            sentiment=risk_class,
        )

        # 写入 topic_posts 关联
        for p in cluster.posts:
            post_id = p.get("post_id", "")
            if post_id:
                add_post_to_topic(topic_id, post_id, is_current=1)

        logger.info(
            f"📦 [TopicAggregator] topic_id={topic_id}, "
            f"topic={cluster.topic_name[:20]}, "
            f"posts={len(cluster.posts)}, "
            f"risk={risk_level} ({risk_class}), "
            f"sentiment={llm_sentiment}, "
            f"core_issue={core_issue[:20] if core_issue else '(空)'}, "
            f"is_new={is_new}"
        )

    @staticmethod
    def _calculate_risk_class(risk_level: int) -> str:
        """risk_level (1-5) → risk_class"""
        if risk_level >= 4:
            return "negative"
        elif risk_level <= 2:
            return "positive"
        return "neutral"
