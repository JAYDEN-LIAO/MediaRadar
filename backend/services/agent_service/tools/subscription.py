"""
A 组 订阅管理 + 意图解析（5 个工具）

设计见 AGENT_REDESIGN.md §4.A。前 4 个工具是订阅 CRUD，
parse_intent 是自然语言入口（解析后渲染 confirm 卡片，
LLM 不应直接接 add_subscription，由用户点确认触发）。

所有工具走 @with_owner，从 contextvar 拿 owner_id，
SQL 强制 per-owner 隔离。
"""
from __future__ import annotations

import json
from typing import Optional

from core.logger import get_logger
from core.model_config_db import get_effective_config
from core.quota_db import check_quota
from core.subscription_db import (
    VALID_POLARITY,
    VALID_PUSH_MODE,
    VALID_SENSITIVITY,
    VALID_TYPES,
    create_subscription,
    delete_subscription,
    get_subscription_by_id,
    list_subscriptions,
    update_subscription,
)

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.subscription")


# ───────────────────────────────────────────────────────────────
# A1. list_subscriptions
# ───────────────────────────────────────────────────────────────
@tool(
    name="list_subscriptions",
    description="列出当前用户的所有订阅及其配置（类型/极性/扫描频率/推送模式）。无参数。",
    parameters=None,
    group="subscription",
)
@with_owner
def list_subscriptions_tool(_owner_id: str) -> str:
    items = list_subscriptions(_owner_id)
    return ToolResult(
        success=True,
        data=items,
        ui={"type": "subscription_list", "data": {"items": items, "count": len(items)}},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# A2. add_subscription
# ───────────────────────────────────────────────────────────────
@tool(
    name="add_subscription",
    description=(
        "新增一个订阅。通常由 parse_intent 卡片确认后调用，"
        "不要在用户没点确认前自动调用此工具。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "订阅对象的名称（人名/品牌/事件/行业/关键词）"},
            "type": {
                "type": "string",
                "enum": list(VALID_TYPES),
                "description": "订阅类型",
            },
            "polarity": {
                "type": "string",
                "enum": list(VALID_POLARITY),
                "description": "关注的情感极性，默认 all",
            },
            "sensitivity": {
                "type": "string",
                "enum": list(VALID_SENSITIVITY),
                "description": "灵敏度，默认 balanced",
            },
            "frequency_min": {
                "type": "integer",
                "minimum": 5,
                "maximum": 1440,
                "description": "扫描间隔（分钟），默认 60",
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定平台；空数组=全平台",
            },
            "push_mode": {
                "type": "string",
                "enum": list(VALID_PUSH_MODE),
                "description": "推送模式：every/important/silent/off，默认 important（由 Agent 决定何时推）",
            },
            "show_risk_alert": {
                "type": "boolean",
                "description": "动态流中是否显示预警，默认 false（v2 默认隐藏预警）",
            },
        },
        "required": ["name", "type"],
    },
    group="subscription",
)
@with_owner
def add_subscription_tool(
    name: str,
    type: str,
    _owner_id: str,
    polarity: str = "all",
    sensitivity: str = "balanced",
    frequency_min: int = 60,
    platforms: Optional[list] = None,
    push_mode: str = "important",
    show_risk_alert: bool = False,
) -> str:
    # 配额检查
    ok, msg = check_quota(_owner_id, "subscription")
    if not ok:
        return ToolResult(
            success=False,
            error=msg,
            error_type="quota_exceeded",
            ui={"type": "ack_text", "data": {"message": msg, "level": "warning"}},
        ).to_json()

    try:
        sub = create_subscription(
            owner_id=_owner_id,
            name=name,
            type=type,
            polarity=polarity,
            sensitivity=sensitivity,
            frequency_min=frequency_min,
            platforms=platforms or [],
            push_mode=push_mode,
            show_risk_alert=show_risk_alert,
        )
    except ValueError as e:
        return ToolResult(
            success=False,
            error=str(e),
            error_type="validation",
        ).to_json()

    return ToolResult(
        success=True,
        data=sub,
        ui={"type": "subscription_card", "data": sub, "action": "added"},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# A3. update_subscription
# ───────────────────────────────────────────────────────────────
@tool(
    name="update_subscription",
    description="修改已有订阅的任一属性。必传 subscription_id（不要用 name，避免重名）。",
    parameters={
        "type": "object",
        "properties": {
            "subscription_id": {"type": "string"},
            "name": {"type": "string"},
            "type": {"type": "string", "enum": list(VALID_TYPES)},
            "polarity": {"type": "string", "enum": list(VALID_POLARITY)},
            "sensitivity": {"type": "string", "enum": list(VALID_SENSITIVITY)},
            "frequency_min": {"type": "integer", "minimum": 5, "maximum": 1440},
            "platforms": {"type": "array", "items": {"type": "string"}},
            "push_mode": {"type": "string", "enum": list(VALID_PUSH_MODE)},
            "show_risk_alert": {"type": "boolean"},
        },
        "required": ["subscription_id"],
    },
    group="subscription",
)
@with_owner
def update_subscription_tool(subscription_id: str, _owner_id: str, **fields) -> str:
    # 先取旧值，方便前端展示 before/after
    before = get_subscription_by_id(_owner_id, subscription_id)
    if not before:
        return ToolResult(
            success=False,
            error=f"订阅不存在或无权限: {subscription_id}",
            error_type="not_found",
        ).to_json()

    try:
        after = update_subscription(_owner_id, subscription_id, **fields)
    except ValueError as e:
        return ToolResult(success=False, error=str(e), error_type="validation").to_json()

    if not after:
        return ToolResult(
            success=False, error="更新失败（订阅可能已被删除）", error_type="not_found"
        ).to_json()

    return ToolResult(
        success=True,
        data={"before": before, "after": after},
        ui={
            "type": "subscription_card",
            "data": after,
            "before": before,
            "action": "updated",
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# A4. remove_subscription
# ───────────────────────────────────────────────────────────────
@tool(
    name="remove_subscription",
    description="删除一个订阅（软删除，is_active=0）。",
    parameters={
        "type": "object",
        "properties": {
            "subscription_id": {"type": "string"},
        },
        "required": ["subscription_id"],
    },
    group="subscription",
)
@with_owner
def remove_subscription_tool(subscription_id: str, _owner_id: str) -> str:
    sub = get_subscription_by_id(_owner_id, subscription_id)
    if not sub:
        return ToolResult(
            success=False,
            error=f"订阅不存在或无权限: {subscription_id}",
            error_type="not_found",
        ).to_json()

    success = delete_subscription(_owner_id, subscription_id)
    if not success:
        return ToolResult(
            success=False, error="删除失败", error_type="db_error"
        ).to_json()

    return ToolResult(
        success=True,
        data={"subscription_id": subscription_id, "name": sub.get("name")},
        ui={
            "type": "subscription_card",
            "data": sub,
            "action": "removed",  # 前端渲染灰色 + 撤销按钮
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# A5. parse_intent — 自然语言订阅入口
#     输出 confirm 卡片，等用户点确认才能 add_subscription
# ───────────────────────────────────────────────────────────────
_INTENT_PROMPT = """\
你是 MediaRadar 的订阅意图解析器。用户用自然语言表达想"关注/盯/订阅"某个对象，\
你需要把它结构化成 JSON。

【类型 type】（必填，五选一）
- person  人物（明星、企业家、政治人物、网红等）
- brand   品牌/产品（手机、汽车、APP、游戏等）
- event   单次事件（演唱会、发布会、自然灾害、突发新闻等）
- industry 行业/领域（新能源、AI、白酒、芯片等）
- keyword 通用关键词（兜底，前 4 类都不合时用）

【情感极性 polarity】
- negative 仅关注负面
- positive 仅关注正面
- neutral 仅关注中性
- all      全部（推荐默认）

【灵敏度 sensitivity】
- conservative 只推真正大事
- balanced     平衡（默认）
- aggressive   宽进，凡有关都推

【推送 push_mode】
- every     每条都推（高强度关注）
- important 由 Agent 决定何时推（默认，推荐）
- silent    不推送，仅在动态流可见
- off       关闭（仅入库）

【场景 scene】
一句话描述用户的关注场景，比如"明星动态" / "品牌口碑" / "产品测评" / "热点跟进" / "行业研究"

【输出格式】严格 JSON，不要任何额外文字：
{{
  "name": "...",
  "type": "...",
  "type_confidence": 0.0~1.0,
  "polarity": "...",
  "sensitivity": "...",
  "push_mode": "...",
  "scene": "...",
  "suggested_platforms": [],
  "suggested_frequency_min": 60,
  "raw_input": "..."
}}

用户输入：{utterance}
"""


@tool(
    name="parse_intent",
    description=(
        "当用户用自然语言描述'我想关注/盯一下/订阅 XX'时优先调此工具。"
        "返回结构化 SubscriptionIntent，前端渲染 confirm_intent 卡片，"
        "用户点确认才能继续 add_subscription。**绝不要在用户点确认前自动调 add_subscription**。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "utterance": {"type": "string", "description": "用户的原始自然语言输入"},
        },
        "required": ["utterance"],
    },
    group="subscription",
)
@with_owner
def parse_intent_tool(utterance: str, _owner_id: str) -> str:
    """调当前用户的 AGENT 模型解析意图。"""
    try:
        cfg = get_effective_config(_owner_id, "AGENT")
    except Exception as e:
        logger.error(f"[parse_intent] 取模型配置失败: {e}")
        return ToolResult(
            success=False,
            error=f"模型配置异常: {e}",
            error_type="config_error",
        ).to_json()

    api_key = cfg.get("api_key")
    if not api_key:
        return ToolResult(
            success=False,
            error="未配置 AGENT 模型 api_key，请到 /admin 或设置页配置默认模型。",
            error_type="config_missing",
        ).to_json()

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=cfg.get("base_url") or None)
        resp = client.chat.completions.create(
            model=cfg.get("model") or "deepseek-chat",
            messages=[
                {"role": "user", "content": _INTENT_PROMPT.format(utterance=utterance)}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=400,
        )
        raw = resp.choices[0].message.content or "{}"
        intent = json.loads(raw)
    except Exception as e:
        logger.error(f"[parse_intent] LLM 调用失败: {e}")
        return ToolResult(
            success=False,
            error=f"意图解析失败: {e}",
            error_type="llm_error",
        ).to_json()

    # 兜底默认值
    intent.setdefault("name", utterance.strip())
    intent.setdefault("type", "keyword")
    intent.setdefault("type_confidence", 0.5)
    intent.setdefault("polarity", "all")
    intent.setdefault("sensitivity", "balanced")
    intent.setdefault("push_mode", "important")
    intent.setdefault("scene", "通用关键词")
    intent.setdefault("suggested_platforms", [])
    intent.setdefault("suggested_frequency_min", 60)
    intent["raw_input"] = utterance

    return ToolResult(
        success=True,
        data=intent,
        ui={
            "type": "intent_preview",
            "data": intent,
            "next_action": "confirm_intent",
        },
    ).to_json()
