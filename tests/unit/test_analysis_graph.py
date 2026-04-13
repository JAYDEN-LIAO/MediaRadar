"""LangGraph 分析子图测试"""
import pytest
from unittest.mock import patch, MagicMock

class TestAnalystNode:
    """Analyst 节点测试"""

    def test_analyst_returns_analyst_result(self):
        from services.radar_service.analysis_graph import analyst_node, RadarGraphState

        state = RadarGraphState(
            mock_post={"title": "测试", "content": "测试内容"},
            keyword="华为",
            sensitivity="balanced",
            level_instruction="",
            status="",
            risk_level=1,
            reason="",
            core_issue="",
            analyst_result={},
            reviewer_result={},
            evolution_timeline={}
        )

        with patch('services.radar_service.analysis_graph.call_llm') as mock_llm:
            from services.radar_service.llm_gateway import LLMCallResult
            mock_llm.return_value = LLMCallResult(
                success=True,
                data={
                    "risk_level": 3,
                    "sentiment": "Negative",
                    "reason": "测试原因",
                    "core_issue": "核心问题",
                    "needs_vision": False
                }
            )

            result = analyst_node(state)

            assert "analyst_result" in result
            assert result["analyst_result"]["risk_level"] == 3

class TestRouteAfterAnalyst:
    """条件路由测试"""

    def test_routes_to_reviewer_when_high_risk(self):
        from services.radar_service.analysis_graph import route_after_analyst, RadarGraphState

        state = RadarGraphState(
            mock_post={"title": "测试", "content": "测试内容"},
            keyword="华为",
            sensitivity="balanced",
            level_instruction="",
            status="",
            risk_level=4,  # 高风险
            reason="",
            core_issue="",
            analyst_result={"risk_level": 4, "sentiment": "Negative"},
            reviewer_result={},
            evolution_timeline={}
        )

        route = route_after_analyst(state)
        assert route == "reviewer"

    def test_routes_to_end_when_low_risk(self):
        from services.radar_service.analysis_graph import route_after_analyst, END, RadarGraphState

        state = RadarGraphState(
            mock_post={"title": "测试", "content": "测试内容"},
            keyword="华为",
            sensitivity="balanced",
            level_instruction="",
            status="",
            risk_level=1,  # 低风险
            reason="",
            core_issue="",
            analyst_result={"risk_level": 1, "sentiment": "Neutral"},
            reviewer_result={},
            evolution_timeline={}
        )

        route = route_after_analyst(state)
        assert route == END

class TestAnalyzeAndReport:
    """analyze_and_report 函数测试"""

    def test_safe_when_no_reviewer(self):
        from services.radar_service.analysis_graph import analyze_and_report

        with patch('services.radar_service.analysis_graph.radar_app') as mock_app:
            mock_app.invoke.return_value = {
                "analyst_result": {"risk_level": 1, "sentiment": "Neutral", "reason": "安全"},
                "reviewer_result": {},
                "final_report": None
            }

            result = analyze_and_report(
                mock_post={"title": "t", "content": "c"},
                keyword="华为"
            )

            assert result["status"] == "safe"
            assert result["risk_level"] == 1
