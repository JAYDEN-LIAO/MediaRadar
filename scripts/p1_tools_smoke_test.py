"""
P1 Agent Tools Smoke Test
==========================

验证 v2.2 P1 阶段的工具体系：
- 7 组 30 个工具全部注册
- @with_owner 强制 owner_id（裸调失败，set_current_owner 后成功）
- 各组取一个无副作用的工具实测，确认返回 JSON 结构

Usage:
    python scripts/p1_tools_smoke_test.py

要求：backend 数据库初始化完成（reset_db.py 已跑过；或直接基于现有 dev DB）
"""
from __future__ import annotations

import json
import os
import sys
import uuid

# 让 import 路径指向 backend/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.agent_service.tools import (
    AVAILABLE_TOOLS,
    STREAMABLE_TOOLS,
    TOOLS_SCHEMA,
    OwnerRequiredError,
    list_tool_names_by_group,
    reset_current_owner,
    set_current_owner,
)


def section(title: str) -> None:
    bar = "─" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


def assert_eq(label: str, got, want):
    ok = got == want
    flag = "✅" if ok else "❌"
    print(f"  {flag} {label}: got={got} want={want}")
    if not ok:
        raise AssertionError(f"{label}: {got} != {want}")


def assert_true(label: str, cond: bool):
    flag = "✅" if cond else "❌"
    print(f"  {flag} {label}")
    if not cond:
        raise AssertionError(label)


def parse_tool_result(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception as e:
        raise AssertionError(f"工具返回非 JSON: {raw[:200]} (err={e})")


# ──────────────────────────────────────────────────────────────
# 1) 注册体系
# ──────────────────────────────────────────────────────────────
section("1) 工具注册体系")

groups = list_tool_names_by_group()
total = sum(len(v) for v in groups.values())
print(f"  组数: {len(groups)}, 工具总数: {total}")
for g, names in groups.items():
    print(f"    [{g}] {len(names)}: {names}")

# P1 期望布局
EXPECT = {
    "system": 6,        # 3 legacy + 3 new
    "subscription": 5,
    "scan": 6,
    "query": 3,
    "push": 4,
    "model": 3,
    "search": 3,
}
for g, n in EXPECT.items():
    assert_eq(f"  group [{g}] count", len(groups.get(g, [])), n)

assert_eq("schema 与 callable 数量一致", len(TOOLS_SCHEMA), len(AVAILABLE_TOOLS))
assert_true("web_search 标记为 streamable", "web_search" in STREAMABLE_TOOLS)
assert_true("schema 长度 = 30", len(TOOLS_SCHEMA) == 30)


# ──────────────────────────────────────────────────────────────
# 2) @with_owner 强制 owner_id
# ──────────────────────────────────────────────────────────────
section("2) @with_owner 强制 owner_id")

list_subs = AVAILABLE_TOOLS["list_subscriptions"]

# 裸调（没 set_current_owner）→ 应抛 OwnerRequiredError
raised = False
try:
    list_subs()
except OwnerRequiredError:
    raised = True
except Exception as e:
    raise AssertionError(f"期望 OwnerRequiredError，实际抛: {type(e).__name__}: {e}")
assert_true("裸调 list_subscriptions 抛 OwnerRequiredError", raised)


# ──────────────────────────────────────────────────────────────
# 3) 用临时 owner 跑各组只读工具
# ──────────────────────────────────────────────────────────────
section("3) 各组只读工具实测")

# 使用一个不会有真实数据的临时 owner id（确保隔离）
fake_owner = f"smoke-{uuid.uuid4().hex[:8]}"
print(f"  使用临时 owner_id: {fake_owner}")
token = set_current_owner(fake_owner)

try:
    # 3.1 A组 list_subscriptions
    res = parse_tool_result(AVAILABLE_TOOLS["list_subscriptions"]())
    assert_true("A.list_subscriptions success=true", res["success"])
    assert_eq("A.list_subscriptions data 是 list", isinstance(res["data"], list), True)
    assert_eq("A.list_subscriptions 空 owner 返回空列表", len(res["data"]), 0)
    print(f"    ui.type = {res['ui']['type']}")

    # 3.2 C组 search_alerts
    res = parse_tool_result(AVAILABLE_TOOLS["search_alerts"](type="all", limit=5))
    assert_true("C.search_alerts success=true", res["success"])
    print(f"    items count = {len(res['data'])}, ui.type = {res['ui']['type']}")

    # 3.3 C组 get_subscription_stats（无订阅 → not_found 也算预期）
    res = parse_tool_result(
        AVAILABLE_TOOLS["get_subscription_stats"](subscription_id="nonexistent")
    )
    print(f"    get_subscription_stats success={res['success']} err_type={res.get('error_type')}")

    # 3.4 D组 list_push_channels
    res = parse_tool_result(AVAILABLE_TOOLS["list_push_channels"]())
    assert_true("D.list_push_channels success=true", res["success"])
    assert_eq("D.list_push_channels 返回 3 通道", len(res["data"]), 3)

    # 3.5 E组 list_models
    res = parse_tool_result(AVAILABLE_TOOLS["list_models"]())
    assert_true("E.list_models success=true", res["success"])
    assert_eq("E.list_models 返回 6 角色", len(res["data"]), 6)
    for item in res["data"]:
        assert_true(
            f"    api_key 不出现明文 ({item['agent_role']})",
            "api_key" not in item,
        )

    # 3.6 F组 list_search_history（应空）
    res = parse_tool_result(AVAILABLE_TOOLS["list_search_history"]())
    assert_true("F.list_search_history success=true", res["success"])
    assert_eq("F.list_search_history 空 owner 返回空", len(res["data"]), 0)

    # 3.7 F组 web_search 占位
    res = parse_tool_result(AVAILABLE_TOOLS["web_search"](query="测试关键词"))
    assert_true("F.web_search success=true (P1 占位)", res["success"])
    assert_eq("F.web_search status=not_implemented", res["data"]["status"], "not_implemented")

    # 3.7b 调完 web_search 后历史应有 1 条
    res = parse_tool_result(AVAILABLE_TOOLS["list_search_history"]())
    assert_eq("F.history 现在 = 1", len(res["data"]), 1)

    # 3.8 G组 health_check
    res = parse_tool_result(AVAILABLE_TOOLS["health_check"]())
    assert_true("G.health_check success=true", res["success"])
    overall = res["data"]["overall"]
    print(f"    health overall = {overall}, components = {len(res['data']['components'])}")
    assert_true("    overall ∈ {ok,warning,error}", overall in ("ok", "warning", "error"))

    # 3.9 G组 get_system_overview
    res = parse_tool_result(AVAILABLE_TOOLS["get_system_overview"]())
    assert_true("G.get_system_overview success=true", res["success"])
    keys = set(res["data"].keys())
    assert_true(
        "    overview 包含 radar/scheduler/today_stats/channels_health/llm_health",
        {"radar", "scheduler", "today_stats", "channels_health", "llm_health"} <= keys,
    )

    # 3.10 G组 get_recent_activity
    res = parse_tool_result(AVAILABLE_TOOLS["get_recent_activity"](minutes=60))
    assert_true("G.get_recent_activity success=true", res["success"])

    # 3.11 B组 get_scan_status (全局，不需要 owner 数据)
    res = parse_tool_result(AVAILABLE_TOOLS["get_scan_status"]())
    assert_true("B.get_scan_status success=true", res["success"])

    # 3.12 B组 get_next_run_time（scheduler 可能未装 apscheduler，允许 dependency_missing）
    res = parse_tool_result(AVAILABLE_TOOLS["get_next_run_time"]())
    if res["success"]:
        print("    B.get_next_run_time success=true")
    else:
        assert_eq(
            "    B.get_next_run_time err_type=dependency_missing (apscheduler 未装)",
            res.get("error_type"),
            "dependency_missing",
        )

    # 3.13 F组 clear_search_cache
    res = parse_tool_result(AVAILABLE_TOOLS["clear_search_cache"]())
    assert_true("F.clear_search_cache success=true", res["success"])
    assert_eq("F.clear_count = 1", res["data"]["cleared_count"], 1)

finally:
    reset_current_owner(token)


# ──────────────────────────────────────────────────────────────
# 4) API 模块可导入（agent_service.api 用 Depends(get_current_user)）
# ──────────────────────────────────────────────────────────────
section("4) /api/agent/* 路由")

from services.agent_service import api as agent_api  # noqa: E402

routes = {(r.path, tuple(sorted(r.methods))) for r in agent_api.router.routes}
print(f"  注册路由数: {len(routes)}")
for p, m in sorted(routes):
    print(f"    {m} {p}")

assert_true("POST /api/agent/chat 存在", ("/api/agent/chat", ("POST",)) in routes)
assert_true("GET /api/agent/memory 存在", ("/api/agent/memory", ("GET",)) in routes)


# ──────────────────────────────────────────────────────────────
# 完成
# ──────────────────────────────────────────────────────────────
print("\n" + "═" * 60)
print("  ✅ P1 smoke test 全部通过")
print("═" * 60)
