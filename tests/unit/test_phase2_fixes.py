"""
Phase 2 升级验收测试（修复 #2.2, #2.3, #2.4, #7.2）

- 2.2: token 估算（char/2，中文偏差 < 20%）
- 2.3: streaming DRY（_stream_response 抽取，4 处统一）
- 2.4: AGENT_MEMORY_WRITES 指标
- 7.2: AGENT_TURNS / AGENT_TOOL_CALLS / AGENT_TOOL_LATENCY + /metrics 端点
"""
import os
import re
import sys
import asyncio
import pytest
from unittest.mock import MagicMock, patch

_BACKEND = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.normpath(_BACKEND))


# ==================== 2.2 token 估算修正 ====================

class TestFix22_TokenEstimate:
    """char/2 估算（修复 #2.2）"""

    def test_count_tokens_chinese(self):
        from services.agent_service.agent_core import TokenBudgetManager
        tbm = TokenBudgetManager(budget=1000)
        # 100 个中文字符，json.dumps(ensure_ascii=False) 后约 ~107 字符（含字段）
        msgs = [{"role": "user", "content": "你好" * 50}]
        tokens = tbm.count_tokens(msgs)
        # 100 中文 ≈ 150 token，char/2 估算应 > 50
        assert tokens > 50, f"中文 token 估算偏低: {tokens}"

    def test_count_tokens_handles_sdk_object(self):
        """ChatCompletionMessage 等 SDK 对象（含 model_dump）"""
        from services.agent_service.agent_core import TokenBudgetManager
        tbm = TokenBudgetManager(budget=1000)

        sdk_msg = MagicMock()
        sdk_msg.model_dump = MagicMock(return_value={"role": "assistant", "content": "ok"})
        tokens = tbm.count_tokens([sdk_msg])
        assert tokens > 0, "SDK 对象应通过 model_dump 转 dict"


# ==================== 2.3 streaming DRY ====================

class TestFix23_StreamingDRY:
    """_stream_response 抽取，agent_core 内不再内联 stream=True（修复 #2.3）"""

    def test_stream_response_helper_exists(self):
        from services.agent_service import agent_core
        assert callable(getattr(agent_core, '_stream_response', None)), \
            "_stream_response helper 必须存在"

    def test_no_inline_stream_true_in_agent_core(self):
        """agent_core.py 内不应再有内联 chat.completions.create(...stream=True)"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'agent_core.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        # 仅 _stream_response 内允许 stream=True
        # 用 DOTALL 跨行匹配 chat.completions.create(...stream=True)
        inline = re.findall(r'chat\.completions\.create\(.*?stream=True', content, re.DOTALL)
        # 仅 _stream_response 内 1 处合法
        assert len(inline) == 1, f"内联 stream=True 应仅出现 1 次（_stream_response 内），实际: {len(inline)}"

    def test_stream_response_call_count(self):
        """主循环应有 4 处调用 _stream_response（trigger / low / medi-degrade / final）"""
        path = os.path.join(_BACKEND, 'services', 'agent_service', 'agent_core.py')
        with open(path, encoding='utf-8') as f:
            content = f.read()
        count = len(re.findall(r'_stream_response\(current_messages\)', content))
        assert count == 4, f"_stream_response 调用数应为 4，实际: {count}"


# ==================== 2.4 + 7.2 Agent 指标 ====================

class TestFix24_72_AgentMetrics:
    """4 个新 Agent 指标 + memory metric（修复 #2.4 / #7.2）"""

    def test_agent_metrics_registered(self):
        """metrics.py 必须导出 4 个 Agent 指标"""
        from core import metrics
        assert hasattr(metrics, 'AGENT_TURNS'), "AGENT_TURNS 未定义"
        assert hasattr(metrics, 'AGENT_TOOL_CALLS'), "AGENT_TOOL_CALLS 未定义"
        assert hasattr(metrics, 'AGENT_TOOL_LATENCY'), "AGENT_TOOL_LATENCY 未定义"
        assert hasattr(metrics, 'AGENT_MEMORY_WRITES'), "AGENT_MEMORY_WRITES 未定义"

    def test_agent_metrics_imported_in_agent_core(self):
        """agent_core.py 必须 import 4 个指标"""
        from services.agent_service import agent_core
        assert hasattr(agent_core, 'AGENT_TURNS')
        assert hasattr(agent_core, 'AGENT_TOOL_CALLS')
        assert hasattr(agent_core, 'AGENT_TOOL_LATENCY')
        assert hasattr(agent_core, 'AGENT_MEMORY_WRITES')

    @pytest.mark.asyncio
    async def test_agent_memory_writes_increments(self):
        """_write_memory_async 成功时 AGENT_MEMORY_WRITES{status=success} +1"""
        from core.metrics import AGENT_MEMORY_WRITES
        from services.agent_service.agent_core import _write_memory_async
        # patch memory_manager.write_from_conversation 避免真写库
        with patch('services.agent_service.agent_core.memory_manager') as mock_mem:
            mock_mem.write_from_conversation = MagicMock(return_value=None)
            before = AGENT_MEMORY_WRITES.labels(status="success")._value.get()
            await _write_memory_async("test-session", [{"role": "user", "content": "hi"}])
            after = AGENT_MEMORY_WRITES.labels(status="success")._value.get()
            assert after - before == 1, f"AGENT_MEMORY_WRITES 未递增: {before} -> {after}"

    @pytest.mark.asyncio
    async def test_agent_memory_writes_error_increments(self):
        """_write_memory_async 失败时 AGENT_MEMORY_WRITES{status=error} +1"""
        from core.metrics import AGENT_MEMORY_WRITES
        from services.agent_service.agent_core import _write_memory_async
        with patch('services.agent_service.agent_core.memory_manager') as mock_mem:
            mock_mem.write_from_conversation = MagicMock(side_effect=Exception("write fail"))
            before = AGENT_MEMORY_WRITES.labels(status="error")._value.get()
            await _write_memory_async("test-session", [{"role": "user", "content": "hi"}])
            after = AGENT_MEMORY_WRITES.labels(status="error")._value.get()
            assert after - before == 1, "失败分支未递增 error 计数"

    @pytest.mark.asyncio
    async def test_tool_executor_records_metrics(self):
        """ToolExecutor.execute 执行后 AGENT_TOOL_CALLS / AGENT_TOOL_LATENCY 应有记录"""
        from core.metrics import AGENT_TOOL_CALLS
        from services.agent_service.agent_core import ToolExecutor

        executor = ToolExecutor()
        # 调用一个支持的工具（get_system_status 是 sync，由 direct adapter 转 async）
        before = AGENT_TOOL_CALLS.labels(tool="get_system_status", status="success")._value.get()
        try:
            await executor.execute("get_system_status", {}, [])
        except Exception:
            pass  # 真实工具失败不影响指标
        after_success = AGENT_TOOL_CALLS.labels(tool="get_system_status", status="success")._value.get()
        after_error = AGENT_TOOL_CALLS.labels(tool="get_system_status", status="error")._value.get()
        # 不论成功/失败都应有一次计数
        assert (after_success > before) or (after_error > 0), "工具调用未被记录"


# ==================== 7.2 /metrics 端点 ====================

class TestFix72_MetricsEndpoint:
    """/metrics 端点必须暴露 Prometheus 文本（修复 #7.2）"""

    def test_metrics_endpoint_exists(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200, f"/metrics 应返回 200，实际: {r.status_code}"

    def test_metrics_endpoint_returns_text_format(self):
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/metrics")
        ct = r.headers.get("content-type", "")
        # CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
        assert "text/plain" in ct, f"Content-Type 应含 text/plain，实际: {ct}"
        # 必须暴露 agent 指标
        body = r.text
        assert "agent_turns_total" in body or "agent_memory_writes_total" in body, \
            "/metrics 必须含 agent_* 指标"


# ==================== 8.1 trace_id middleware ====================

class TestFix81_TraceIdMiddleware:
    """8.1：HTTP 请求级 trace_id 中间件 + 日志注入 + 响应头回写"""

    def test_context_helpers_exist(self):
        from core.context import set_trace_id, get_trace_id, generate_trace_id, clear_trace_id
        assert callable(set_trace_id) and callable(get_trace_id)
        assert callable(generate_trace_id) and callable(clear_trace_id)

    def test_trace_id_isolated_from_task_id(self):
        """trace_id 与 task_id 独立存储（ContextVar 解耦）"""
        from core.context import set_trace_id, get_trace_id, set_task_context, get_task_context, clear_trace_id
        set_task_context(task_id="task-xxx", keyword="测试")
        set_trace_id("trace-yyy")
        assert get_trace_id() == "trace-yyy"
        assert get_task_context().task_id == "task-xxx"
        clear_trace_id()
        # 清掉 trace_id 后，task_id 应仍存在
        assert get_task_context().task_id == "task-xxx"
        assert get_trace_id() == ""

    def test_generate_trace_id_is_uuid_hex(self):
        from core.context import generate_trace_id
        tid = generate_trace_id()
        assert isinstance(tid, str)
        assert len(tid) == 32, "uuid4().hex 长度应为 32"
        assert "-" not in tid

    def test_middleware_generates_trace_id(self):
        """无 X-Trace-Id header 时，middleware 自动生成"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        r = client.get("/metrics")
        assert "x-trace-id" in {k.lower() for k in r.headers.keys()}
        trace_id = r.headers.get("x-trace-id") or r.headers.get("X-Trace-Id")
        assert trace_id and len(trace_id) == 32, f"应生成 32 字符 hex trace_id，实际: {trace_id!r}"

    def test_middleware_preserves_incoming_trace_id(self):
        """入站带 X-Trace-Id 时，原样回写（便于上游链路串联）"""
        from fastapi.testclient import TestClient
        from gateway.main import app
        client = TestClient(app)
        incoming = "abc123def4567890abc123def45678900"  # 32 字符
        r = client.get("/metrics", headers={"X-Trace-Id": incoming})
        echoed = r.headers.get("x-trace-id") or r.headers.get("X-Trace-Id")
        assert echoed == incoming, f"X-Trace-Id 应原样回写: 收 {incoming}, 出 {echoed}"

    def test_trace_id_filter_attaches_to_record(self):
        """TraceIdFilter 应将 ContextVar 中的 trace_id 注入 LogRecord"""
        import logging
        from core.context import set_trace_id, clear_trace_id
        from core.logger import TraceIdFilter

        f = TraceIdFilter()
        set_trace_id("trace-test-12345")
        rec = logging.LogRecord("t", logging.INFO, "x.py", 1, "m", None, None)
        assert f.filter(rec) is True
        assert rec.trace_id == "trace-test-12345"
        clear_trace_id()

    def test_colored_formatter_renders_trace_id(self):
        """ColoredConsoleFormatter 应在含 trace_id 时渲染 [t:...]"""
        import logging
        from core.logger import ColoredConsoleFormatter

        fmt = ColoredConsoleFormatter(use_color=False)
        rec = logging.LogRecord("t", logging.INFO, "x.py", 1, "hello", None, None)
        rec.trace_id = "abcd1234efgh"
        out = fmt.format(rec)
        assert "[t:abcd1234]" in out, f"应渲染 trace_id 前 8 字符: {out}"
