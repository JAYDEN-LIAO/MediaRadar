"""话题追踪模块测试"""
import pytest
from unittest.mock import patch, MagicMock

class TestBuildTopicId:
    """话题 ID 生成测试"""

    def test_topic_id_is_deterministic(self):
        from services.radar_service.topic_tracker import build_topic_id

        id1 = build_topic_id("华为", "新品发布")
        id2 = build_topic_id("华为", "新品发布")
        id3 = build_topic_id("华为", "其他话题")

        assert id1 == id2  # 相同输入应产生相同 ID
        assert id1 != id3   # 不同输入应产生不同 ID
        assert len(id1) == 32  # MD5 固定长度

class TestBuildEvolutionTimeline:
    """演化时间线构造测试"""

    def test_new_topic_has_no_history(self):
        from services.radar_service.topic_tracker import build_evolution_timeline

        result = build_evolution_timeline(
            current_topic={"topic_name": "新话题", "keyword": "华为", "risk_level": 2},
            similar_topics=[]  # 无历史话题
        )

        assert result["is_new_topic"] is True
        assert result["risk_evolution_path"] == ""

    def test_existing_topic_has_evolution_path(self):
        from services.radar_service.topic_tracker import build_evolution_timeline

        result = build_evolution_timeline(
            current_topic={"topic_name": "持续话题", "keyword": "华为", "risk_level": 3},
            similar_topics=[
                {"topic_name": "持续话题", "risk_level": 2, "first_seen": "2026-01-01", "last_seen": "2026-03-01", "scan_count": 2, "post_count": 5, "platforms": ["wb"], "core_issue": "问题1"}
            ]
        )

        assert result["is_new_topic"] is False
        assert "→" in result["risk_evolution_path"]  # "2 → 3"

    def test_escalating_signal_when_risk_increases(self):
        from services.radar_service.topic_tracker import build_evolution_timeline

        result = build_evolution_timeline(
            current_topic={"topic_name": "升级话题", "keyword": "华为", "risk_level": 4},
            similar_topics=[
                {"topic_name": "升级话题", "risk_level": 2, "first_seen": "2026-01-01", "last_seen": "2026-02-01", "scan_count": 1, "post_count": 3, "platforms": ["wb"], "core_issue": "初始"},
                {"topic_name": "升级话题", "risk_level": 3, "first_seen": "2026-01-01", "last_seen": "2026-03-01", "scan_count": 2, "post_count": 5, "platforms": ["wb"], "core_issue": "升级"}
            ]
        )

        assert result["evolution_signal"] == "escalating"
