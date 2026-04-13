"""LLM Gateway 错误处理 + CircuitBreaker 测试"""
import pytest
from unittest.mock import MagicMock, patch

class TestLLMCallResult:
    """LLMCallResult 数据类测试"""

    def test_success_result(self):
        from services.radar_service.llm_gateway import LLMCallResult

        result = LLMCallResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.is_valid is True
        assert result.error is None

    def test_failure_result(self):
        from services.radar_service.llm_gateway import LLMCallResult

        result = LLMCallResult(success=False, error="JSONDecodeError: ...")
        assert result.success is False
        assert result.is_valid is False
        assert "JSONDecodeError" in result.error

    def test_invalid_when_data_is_none(self):
        from services.radar_service.llm_gateway import LLMCallResult

        # success=True 但 data=None 也是无效的
        result = LLMCallResult(success=True, data=None)
        assert result.is_valid is False

class TestCircuitBreaker:
    """CircuitBreaker 熔断测试"""

    def test_circuit_breaker_opens_after_threshold(self):
        from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)

        # 连续失败 3 次
        for i in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state.value == "open"

        # OPEN 状态下调用应立即抛出异常
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not run")

    def test_circuit_breaker_half_open_after_timeout(self):
        import time
        from core.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)

        # 触发熔断
        for i in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state.value == "open"

        # 等待 recovery_timeout
        time.sleep(0.15)

        # 再次调用应进入 HALF_OPEN
        cb.call(lambda: "success")
        assert cb.state.value == "closed"

    def test_circuit_breaker_success_resets(self):
        from core.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=3)

        # 成功调用
        cb.call(lambda: "result")
        assert cb.state.value == "closed"
        assert cb._failures == 0

class TestCallLLMWithMocks:
    """call_llm 错误处理测试"""

    def test_json_decode_error_returns_failure_result(self):
        from services.radar_service.llm_gateway import LLMCallResult

        with patch('services.radar_service.llm_gateway.deepseek_client') as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "not valid json {"
            mock_client.chat.completions.create.return_value = mock_response

            from services.radar_service.llm_gateway import call_llm
            result = call_llm("system prompt", "user text", response_format="json")

            assert isinstance(result, LLMCallResult)
            assert result.success is False
            # 错误消息包含 "JSON" 和原始内容
            assert "JSON" in result.error and "not valid json" in result.error
