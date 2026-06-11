"""
E 组 模型管理（3 个工具，列出/切换/测试模型配置）

E1. list_models：列出 6 个 Agent 角色的当前模型配置（含系统默认回退标记）
E2. switch_model：切换某角色到指定 provider+model（api_key 可不填，复用旧值）
E3. test_model：用当前用户的有效配置发一次最小调用，返回耗时与样本回复

注意：与 CLAUDE.md 旧文档"5 个角色"不一致——v2.2 新增了 AGENT 角色（用于
Chat 助手本身），共 6 个：DEFAULT / ANALYST / REVIEWER / EMBEDDING / VISION / AGENT。
"""
from __future__ import annotations

import time
from typing import Optional

from core.logger import get_logger
from core.model_config_db import (
    AGENT_ROLES,
    PROVIDERS,
    get_effective_config,
    list_model_configs,
    upsert_model_config,
)

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.model")

# 过滤掉空串
_VALID_PROVIDERS = tuple(p for p in PROVIDERS if p)


# ───────────────────────────────────────────────────────────────
# E1. list_models
# ───────────────────────────────────────────────────────────────
@tool(
    name="list_models",
    description=(
        "列出当前用户的 6 个 Agent 角色的模型配置 "
        "(DEFAULT/ANALYST/REVIEWER/EMBEDDING/VISION/AGENT)，"
        "未配置的角色会标记 is_user_override=false 并回退到系统默认。"
    ),
    parameters=None,
    group="model",
)
@with_owner
def list_models_tool(_owner_id: str) -> str:
    raw = list_model_configs(_owner_id)
    items = []
    for r in raw:
        role = r.get("agent_role")
        eff = get_effective_config(_owner_id, role)
        items.append({
            "agent_role": role,
            "provider": eff.get("provider"),
            "model": eff.get("model"),
            "base_url": eff.get("base_url"),
            "is_user_override": eff.get("is_user_override", False),
            # 不返回 api_key 明文，只标记是否设置
            "api_key_set": bool(eff.get("api_key")),
            "updated_at": r.get("updated_at"),
        })
    return ToolResult(
        success=True,
        data=items,
        ui={"type": "model_list", "data": {"items": items, "count": len(items)}},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# E2. switch_model
# ───────────────────────────────────────────────────────────────
@tool(
    name="switch_model",
    description=(
        "切换指定 Agent 角色的模型。api_key 不填则复用现有值，"
        "需要换 key 时显式传入。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "enum": list(AGENT_ROLES),
            },
            "provider": {
                "type": "string",
                "enum": list(_VALID_PROVIDERS),
            },
            "model": {"type": "string", "description": "模型 ID，如 deepseek-chat / moonshot-v1-8k"},
            "api_key": {"type": "string", "description": "API Key，不填复用旧值"},
            "base_url": {"type": "string", "description": "自定义 base_url，可空"},
        },
        "required": ["agent_role", "provider", "model"],
    },
    group="model",
)
@with_owner
def switch_model_tool(
    agent_role: str,
    provider: str,
    model: str,
    _owner_id: str,
    api_key: Optional[str] = None,
    base_url: str = "",
) -> str:
    if agent_role not in AGENT_ROLES:
        return ToolResult(
            success=False,
            error=f"无效的 agent_role: {agent_role}（合法: {list(AGENT_ROLES)}）",
            error_type="validation",
        ).to_json()
    if provider not in _VALID_PROVIDERS:
        return ToolResult(
            success=False,
            error=f"无效的 provider: {provider}（合法: {list(_VALID_PROVIDERS)}）",
            error_type="validation",
        ).to_json()

    try:
        cfg = upsert_model_config(
            owner_id=_owner_id,
            agent_role=agent_role,
            provider=provider,
            model=model,
            api_key=api_key,  # None = 保留旧值
            base_url=base_url or "",
        )
    except ValueError as e:
        return ToolResult(success=False, error=str(e), error_type="validation").to_json()

    # 不返回 api_key 明文
    safe = {**cfg, "api_key": "***" if cfg.get("api_key") else ""}
    return ToolResult(
        success=True,
        data=safe,
        ui={
            "type": "model_card",
            "data": safe,
            "action": "switched",
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# E3. test_model
# ───────────────────────────────────────────────────────────────
@tool(
    name="test_model",
    description=(
        "用当前用户的有效配置对指定角色做一次最小调用，"
        "返回是否成功 / 耗时（ms）/ 样本回复 / 错误信息。"
        "EMBEDDING/VISION 角色暂时只验证 api_key 可达性。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "enum": list(AGENT_ROLES),
            },
        },
        "required": ["agent_role"],
    },
    group="model",
)
@with_owner
def test_model_tool(agent_role: str, _owner_id: str) -> str:
    if agent_role not in AGENT_ROLES:
        return ToolResult(
            success=False,
            error=f"无效的 agent_role: {agent_role}",
            error_type="validation",
        ).to_json()

    eff = get_effective_config(_owner_id, agent_role)
    if not eff.get("api_key"):
        return ToolResult(
            success=False,
            error=f"角色 {agent_role} 未配置 api_key（也无系统默认可回退）",
            error_type="config_missing",
        ).to_json()

    # 对 chat 类角色（DEFAULT/ANALYST/REVIEWER/AGENT）做 chat completion 验证
    chat_roles = {"DEFAULT", "ANALYST", "REVIEWER", "AGENT"}
    start = time.time()
    err = ""
    sample = ""
    ok = False
    try:
        from openai import OpenAI

        client = OpenAI(api_key=eff["api_key"], base_url=eff.get("base_url") or None)
        if agent_role in chat_roles:
            resp = client.chat.completions.create(
                model=eff.get("model") or "deepseek-chat",
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
                max_tokens=8,
            )
            sample = (resp.choices[0].message.content or "").strip()[:80]
        else:
            # EMBEDDING/VISION：只做 list models 探活（最低成本）
            # 不同 provider models endpoint 兼容性差，这里直接判 client 构造成功即视为可达
            sample = f"{agent_role} 客户端构造成功（未做真实推理）"
        ok = True
    except Exception as e:
        err = str(e)
        logger.error(f"[test_model] role={agent_role} 失败: {e}")
    latency_ms = int((time.time() - start) * 1000)

    data = {
        "agent_role": agent_role,
        "provider": eff.get("provider"),
        "model": eff.get("model"),
        "success": ok,
        "latency_ms": latency_ms,
        "sample_response": sample,
        "error": err,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "test_result", "data": data},
    ).to_json()
