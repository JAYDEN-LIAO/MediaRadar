"""
P2 SSE 协议联调脚本
====================

验证 v2.2 P2 阶段 SSE 多事件协议：
1. sse.py 事件工厂输出 wire 格式正确
2. /api/agent/chat 路由走 auth + 返回 text/event-stream
3. 端到端模拟 LLM → 解析所有事件类型

运行：
    python scripts/p2_sse_smoke_test.py

不需要真实 LLM 也不需要起服务（用 FastAPI TestClient + monkey-patch LLM 客户端）。
"""
from __future__ import annotations

import json
import os
import sys
import time

# ── bootstrap ──
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from fastapi.testclient import TestClient

from gateway.main import app  # noqa: E402
from services.agent_service import sse  # noqa: E402
from services.agent_service.sse import (  # noqa: E402
    emit_done,
    emit_error,
    emit_text,
    emit_tool_call,
    emit_tool_progress,
    emit_tool_result,
)


# ═══════════════════════════════════════════════════════════════
# 1) sse.py 工厂单元测试
# ═══════════════════════════════════════════════════════════════
def section(title):
    print(f"\n── {title} " + "─" * (60 - len(title) - 5))


def assert_eq(label, got, want):
    ok = got == want
    print(f"  {'✅' if ok else '❌'} {label}: got={got!r} want={want!r}")
    if not ok:
        raise AssertionError(label)


def assert_true(label, cond):
    print(f"  {'✅' if cond else '❌'} {label}")
    if not cond:
        raise AssertionError(label)


section("1) sse.py 事件工厂")

# text
out = emit_text("hello world")
assert_eq("text 单行", out, 'event: text\ndata: "hello world"\n\n')

# text 多行 → 必须 JSON 编码（避免换行打乱 SSE 帧）
out = emit_text("line1\nline2")
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("text JSON 解码后含换行", parsed, "line1\nline2")

# tool_call
out = emit_tool_call("c1", "foo", {"x": 1})
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("tool_call call_id", parsed["call_id"], "c1")
assert_eq("tool_call tool", parsed["tool"], "foo")
assert_eq("tool_call args", parsed["args"], {"x": 1})

# tool_progress
out = emit_tool_progress("c1", {"type": "item", "item": {"title": "x"}})
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("tool_progress partial", parsed["partial"], {"type": "item", "item": {"title": "x"}})

# tool_result 完整字段
out = emit_tool_result("c1", True, data={"k": "v"}, ui={"type": "card"}, error="")
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("tool_result success", parsed["success"], True)
assert_eq("tool_result data", parsed["data"], {"k": "v"})
assert_eq("tool_result ui.type", parsed["ui"]["type"], "card")
assert_eq("tool_result error", parsed["error"], "")

# tool_result 失败场景
out = emit_tool_result("c1", False, error="oops", error_type="validation")
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("tool_result fail success", parsed["success"], False)
assert_eq("tool_result fail err_type", parsed["error_type"], "validation")

# error
out = emit_error("boom", "internal", call_id="c1")
parsed = json.loads(out.split("data: ", 1)[1].rstrip("\n"))
assert_eq("error call_id", parsed.get("call_id"), "c1")
assert_eq("error msg", parsed["message"], "boom")

# done
out = emit_done()
assert_eq("done 固定格式", out, "event: done\ndata:\n\n")

# 全集合：emit_text/emit_tool_call/emit_tool_progress/emit_tool_result/emit_error/emit_done 都已暴露
all_emits = [n for n in dir(sse) if n.startswith("emit_")]
assert_eq("sse 模块暴露事件数", len(all_emits), 6)


# ═══════════════════════════════════════════════════════════════
# 2) /api/agent/chat Header 验证
# ═══════════════════════════════════════════════════════════════
section("2) /api/agent/chat 端点 header")

client = TestClient(app)

# 2.1 无 token → 401
r = client.post("/api/agent/chat", json={"messages": [{"role": "user", "content": "ping"}]})
assert_eq("无 token 401", r.status_code, 401)


# ═══════════════════════════════════════════════════════════════
# 3) 端到端：注册→登录→发 chat→解析事件
# ═══════════════════════════════════════════════════════════════
section("3) E2E：注册 + 登录 + chat 事件流")

import secrets
username = f"p2user_{secrets.token_hex(4)}"
email = f"{username}@p2test.local"
password = "P2test123!"

# 3.1 注册
r = client.post(
    "/api/auth/register",
    json={"username": username, "email": email, "password": password},
)
assert_true(f"注册成功 (status={r.status_code})", r.status_code in (200, 201))
reg_data = r.json().get("data") or r.json()
token = reg_data.get("access_token") or reg_data.get("token")
assert_true("拿到 access_token", bool(token))
user_id = reg_data.get("user", {}).get("id") or reg_data.get("id")
print(f"    user_id={user_id}")

# 3.2 monkey-patch LLM 客户端 → 模拟 tool_call + 文本流
#    第一轮：list_subscriptions tool_call → 我们的真工具 → tool_result
#    第二轮：纯文本回复
from unittest.mock import MagicMock

from services.agent_service import agent_core


# 用 module-level state 保证多次 _get_agent_client 共享同一轮次
_fake_state = {"iter": iter([1, 2])}


def _fake_create(model, messages, tools=None, **kw):
    try:
        m = next(_fake_state["iter"])
    except StopIteration:
        m = 2  # 默认当文本
    if m == 1:
        msg = MagicMock()
        msg.content = ""
        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "list_subscriptions"
        tc.function.arguments = "{}"
        msg.tool_calls = [tc]
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        return resp
    # 文本流
    class FakeChunk:
        def __init__(self, content):
            self.choices = [MagicMock(delta=MagicMock(content=content))]

    return iter([FakeChunk(c) for c in ["我", "帮你", "查", "一下", "。\n"]])


def _fake_get_agent_client():
    fake = MagicMock()
    fake.chat.completions.create = _fake_create
    return fake


agent_core._get_agent_client = _fake_get_agent_client

# 3.3 POST chat（SSE 流式）
# TestClient.send(stream=True) 返回 Response，需在 response 关闭前读完 body
print("  ⏳ 发送 chat 请求...")
events: list = []
raw_request = client.build_request(
    "POST",
    "/api/agent/chat",
    headers={"Authorization": f"Bearer {token}"},
    json={"messages": [{"role": "user", "content": "我订阅了啥？"}]},
)
r = client.send(raw_request, stream=True)
try:
    assert_eq("SSE 200", r.status_code, 200)
    ct = r.headers.get("content-type", "")
    assert_true(f"Content-Type = text/event-stream (实际: {ct})", "text-event-stream" in ct or "text/event-stream" in ct)

    # 3.4 解析 SSE 流（一次性 read 全部 body，再按行切）
    body_bytes = r.read()
    body = body_bytes.decode("utf-8", errors="replace")
    print(f"  📦 body 长度={len(body)} 字符")
    data_buf: list = []
    current_event = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data:"):
            data_buf.append(line[5:] if line.startswith("data: ") else "")
        elif line == "":
            if current_event is not None:
                payload = "\n".join(data_buf) if data_buf else ""
                events.append((current_event, payload))
                current_event = None
                data_buf = []
finally:
    r.close()

# 3.5 事件类型分布
from collections import Counter

type_counts = Counter(e for e, _ in events)
print(f"  收到事件 {len(events)} 条：{dict(type_counts)}")
assert_true("有 tool_call 事件", "tool_call" in type_counts)
assert_true("有 tool_result 事件", "tool_result" in type_counts)
assert_true("有 text 事件", "text" in type_counts)
assert_true("有 done 事件", "done" in type_counts)

# 3.6 校验 tool_call payload
tc_events = [(e, p) for e, p in events if e == "tool_call"]
tc = json.loads(tc_events[0][1])
assert_eq("tool_call.tool", tc["tool"], "list_subscriptions")
assert_true("tool_call.args 是 dict", isinstance(tc["args"], dict))
assert_true("tool_call.call_id 存在", "call_id" in tc)

# 3.7 校验 tool_result payload
tr_events = [(e, p) for e, p in events if e == "tool_result"]
tr = json.loads(tr_events[0][1])
assert_eq("tool_result.success", tr["success"], True)
assert_true("tool_result.ui.type 存在", "type" in tr.get("ui", {}))
assert_eq("tool_result.ui.type", tr["ui"]["type"], "subscription_list")

# 3.8 done 是最后一个事件
assert_eq("最后事件是 done", events[-1][0], "done")
assert_eq("done 数据为空", events[-1][1], "")

# 3.9 错误事件（如果出现）必须有 call_id
err_events = [(e, p) for e, p in events if e == "error"]
if err_events:
    err = json.loads(err_events[0][1])
    assert_true("error 含 call_id", "call_id" in err)
    assert_true("error 含 message", "message" in err)

# ═══════════════════════════════════════════════════════════════
section("P2 协议联调 ✅ 全部通过")
print("=" * 60)
print("  ✅ P2 SSE 协议联调脚本全部通过")
print("=" * 60)
