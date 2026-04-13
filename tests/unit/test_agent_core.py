"""Agent 核心流式对话 + 工具退避测试"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch

class TestToolBackoff:
    """工具指数退避测试"""

    @pytest.mark.asyncio
    async def test_tool_retries_3_times_on_failure(self):
        from services.agent_service.agent_core import execute_tool_with_backoff

        call_count = 0
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("工具执行失败")

        result = await execute_tool_with_backoff(
            "test_tool",
            failing_func,
            {}
        )

        assert call_count == 3  # 重试 3 次
        assert "工具执行失败" in result

    @pytest.mark.asyncio
    async def test_tool_succeeds_on_second_attempt(self):
        from services.agent_service.agent_core import execute_tool_with_backoff

        call_count = 0
        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("临时失败")
            return '{"status": "ok"}'

        result = await execute_tool_with_backoff(
            "test_tool",
            eventually_succeeds,
            {}
        )

        assert call_count == 2
        assert "ok" in result

class TestSSEFormat:
    """SSE 格式测试"""

    @pytest.mark.asyncio
    async def test_sse_yield_format(self):
        """验证 SSE yield 格式为 data: 内容\\n\\n"""
        from services.agent_service.agent_core import chat_with_agent_stream

        # Mock 让模型直接返回无工具调用的响应
        with patch('services.agent_service.agent_core.agent_client') as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].message.content = "测试回复"
            mock_client.chat.completions.create.return_value = mock_response

            # 消费 async generator
            chunks = []
            async for chunk in chat_with_agent_stream([]):
                chunks.append(chunk)

            # 验证格式
            for chunk in chunks:
                if chunk.startswith("data:") and "[DONE]" not in chunk:
                    assert chunk.endswith("\n\n"), f"SSE chunk should end with \\n\\n: {chunk!r}"

    @pytest.mark.asyncio
    async def test_sse_done_signal(self):
        """验证 [DONE] 结束信号"""
        from services.agent_service.agent_core import chat_with_agent_stream

        with patch('services.agent_service.agent_core.agent_client') as mock_client:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].message.content = "完成"
            mock_client.chat.completions.create.return_value = mock_response

            chunks = []
            async for chunk in chat_with_agent_stream([]):
                chunks.append(chunk)

            # 最后一帧应为 data: [DONE]\n\n
            done_chunks = [c for c in chunks if "[DONE]" in c]
            assert len(done_chunks) > 0
            assert done_chunks[-1] == "data: [DONE]\n\n"
