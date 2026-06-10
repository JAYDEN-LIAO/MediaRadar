"""
D 组 推送通道管理（4 个工具，AGENT_REDESIGN.md §4.D 落 P1 版本）

D1. list_push_channels：列出当前用户的全部通道（含未配置的占位）
D2. toggle_channel：开关单个通道
D3. test_channel：用当前用户的配置发一条测试消息（带 latency）
D4. update_channel_config：合并写入通道配置（不会清空已有字段）

P1 限制：
- RSS 通道暂未实现（PushChannel 枚举只有 email/wecom/feishu），
  传 channel=rss 会被拒；后续 P9/P10 再补。
- 测试发送走全局 NotifierRegistry，会读 settings 的全局配置作为兜底；
  传入的 config 优先级最高。
"""
from __future__ import annotations

import time
from typing import Optional

from core.logger import get_logger
from services.radar_service.db_manager import (
    get_all_push_configs,
    get_push_config,
    save_push_config,
)
from services.radar_service.notifier import reload_registry, test_channel
from services.radar_service.notifier.models import PushChannel

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.push")

# P1 已实现的通道（RSS 待 P9）
_SUPPORTED_CHANNELS = ("email", "wecom", "feishu")


def _to_channel_enum(channel: str) -> Optional[PushChannel]:
    try:
        return PushChannel(channel)
    except ValueError:
        return None


# ───────────────────────────────────────────────────────────────
# D1. list_push_channels
# ───────────────────────────────────────────────────────────────
@tool(
    name="list_push_channels",
    description=(
        "列出当前用户的所有推送通道（邮箱/企业微信/飞书）"
        "及其启用状态、最低风险等级。无参数。"
    ),
    parameters=None,
    group="push",
)
@with_owner
def list_push_channels_tool(_owner_id: str) -> str:
    cfgs = get_all_push_configs(owner_id=_owner_id)
    items = []
    for ch in _SUPPORTED_CHANNELS:
        c = cfgs.get(ch) or {}
        items.append({
            "channel": ch,
            "enabled": bool(c.get("enabled", False)),
            "risk_min_level": int(c.get("risk_min_level", 2)),
            "configured": any(
                k for k in c.keys()
                if k not in ("enabled", "risk_min_level")
            ),
        })
    return ToolResult(
        success=True,
        data=items,
        ui={"type": "channel_list", "data": {"items": items, "count": len(items)}},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# D2. toggle_channel
# ───────────────────────────────────────────────────────────────
@tool(
    name="toggle_channel",
    description="启用或关闭一个推送通道（不影响通道里的具体配置）。",
    parameters={
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": list(_SUPPORTED_CHANNELS),
            },
            "enabled": {"type": "boolean"},
        },
        "required": ["channel", "enabled"],
    },
    group="push",
)
@with_owner
def toggle_channel_tool(channel: str, enabled: bool, _owner_id: str) -> str:
    if channel not in _SUPPORTED_CHANNELS:
        return ToolResult(
            success=False,
            error=f"不支持的通道: {channel}（P1 支持 email/wecom/feishu）",
            error_type="validation",
        ).to_json()

    cfg = get_push_config(_owner_id, channel)
    cfg["enabled"] = bool(enabled)
    save_push_config(_owner_id, channel, cfg)
    reload_registry()  # 热重载（影响全局 registry，P6 后改 per-user）

    return ToolResult(
        success=True,
        data={"channel": channel, "enabled": cfg["enabled"], "config": cfg},
        ui={
            "type": "channel_card",
            "data": {"channel": channel, "enabled": cfg["enabled"], "config": cfg},
            "action": "toggled",
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# D3. test_channel
# ───────────────────────────────────────────────────────────────
@tool(
    name="test_channel",
    description=(
        "向指定通道发送一条测试消息，返回是否成功 + 耗时。"
        "用户问'测一下邮箱能不能用'、'看看飞书还通不通'时调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": list(_SUPPORTED_CHANNELS),
            },
            "message": {
                "type": "string",
                "description": "测试消息文本（注：当前版本未使用，固定模板）",
            },
        },
        "required": ["channel"],
    },
    group="push",
)
@with_owner
def test_channel_tool(channel: str, _owner_id: str, message: Optional[str] = None) -> str:
    ch_enum = _to_channel_enum(channel)
    if ch_enum is None:
        return ToolResult(
            success=False,
            error=f"不支持的通道: {channel}",
            error_type="validation",
        ).to_json()

    cfg = get_push_config(_owner_id, channel)
    if not cfg:
        return ToolResult(
            success=False,
            error=f"未配置 {channel} 通道，先用 update_channel_config 配置后再测",
            error_type="config_missing",
        ).to_json()

    start = time.time()
    err = ""
    try:
        ok = test_channel(ch_enum, cfg)
    except Exception as e:
        ok = False
        err = str(e)
        logger.error(f"[test_channel] {channel} 测试异常: {e}")
    latency_ms = int((time.time() - start) * 1000)

    data = {
        "channel": channel,
        "success": bool(ok),
        "latency_ms": latency_ms,
        "error": err,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "test_result", "data": data},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# D4. update_channel_config
# ───────────────────────────────────────────────────────────────
@tool(
    name="update_channel_config",
    description=(
        "更新某通道的配置字段（合并写入，不会清掉未传的字段）。"
        "email 需 smtp_host/smtp_port/sender_email/sender_password/receiver_email；"
        "wecom/feishu 需 webhook。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "enum": list(_SUPPORTED_CHANNELS),
            },
            "config": {
                "type": "object",
                "description": "通道配置 KV，会与已有配置 merge",
            },
        },
        "required": ["channel", "config"],
    },
    group="push",
)
@with_owner
def update_channel_config_tool(channel: str, config: dict, _owner_id: str) -> str:
    if channel not in _SUPPORTED_CHANNELS:
        return ToolResult(
            success=False,
            error=f"不支持的通道: {channel}",
            error_type="validation",
        ).to_json()
    if not isinstance(config, dict):
        return ToolResult(
            success=False,
            error="config 必须是对象",
            error_type="validation",
        ).to_json()

    old = get_push_config(_owner_id, channel) or {}
    merged = {**old, **config}
    save_push_config(_owner_id, channel, merged)
    reload_registry()

    return ToolResult(
        success=True,
        data={"channel": channel, "before": old, "after": merged},
        ui={
            "type": "channel_card",
            "data": {"channel": channel, "config": merged},
            "before": old,
            "action": "updated",
        },
    ).to_json()
