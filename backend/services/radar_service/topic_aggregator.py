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

        # 风险映射
        risk_level = analysis_result.get("risk_level", 2)
        risk_class = self._calculate_risk_class(risk_level)

        # 平台列表
        platforms = list({p.get("platform", cluster.keyword) for p in cluster.posts})
        # 转为中文
        plat_name_map = {
            "wb": "微博", "xhs": "小红书", "bili": "B站",
            "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"
        }
        platforms_cn = [plat_name_map.get(p, p) for p in platforms]

        # 核心问题取分析结果
        core_issue = analysis_result.get("core_issue", "")
        report = analysis_result.get("report", "")

        # 话题摘要（如果 AnalysisSubGraph 已生成则复用，否则传空）
        cluster_summary = analysis_result.get("cluster_summary", "")

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
