"""
F 组 全网搜索（3 个工具，AGENT_REDESIGN.md §4.F 落 P1 版本）

F1. web_search ⭐ streamable
    P1 占位实现：search_service 模块未上线（P9 接入 Pipeline mode=quick_search），
    本工具暂返回"功能待上线"提示并写一条 history 占位条。
    保留 streamable=True 标记，方便 P2 SSE 升级后无缝替换。
F2. list_search_history：返回当前用户的会话内搜索历史
F3. clear_search_cache：清空当前用户的搜索缓存
"""
from __future__ import annotations

from typing import Optional

from core.logger import get_logger

from .._search_cache import clear_history, list_history, record_search
from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.search")


# ───────────────────────────────────────────────────────────────
# F1. web_search （streamable=True，P1 占位）
# ───────────────────────────────────────────────────────────────
@tool(
    name="web_search",
    description=(
        "跨平台全网搜索（实时拉取，不入库）。"
        "和 search_alerts 区别：本工具是即时搜索；search_alerts 查库历史。"
        "⚠️ P1 暂未接 search_service，只返回占位结果，P9 上线。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定平台；空 = 全平台",
            },
            "max_per_platform": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "每平台最多返回条数，默认 5",
            },
            "time_range": {
                "type": "string",
                "enum": ["1d", "7d", "30d", "all"],
                "description": "时间范围，默认 7d",
            },
        },
        "required": ["query"],
    },
    group="search",
    streamable=True,
)
@with_owner
def web_search_tool(
    query: str,
    _owner_id: str,
    platforms: Optional[list] = None,
    max_per_platform: int = 5,
    time_range: str = "7d",
) -> str:
    # P1 占位
    record_search(_owner_id, query, 0)
    msg = (
        "web_search 功能待 P9 接入 backend/services/search_service/ 模块。"
        "P1 阶段请用 search_alerts 查历史数据，或 trigger_scan 重新抓取。"
    )
    data = {
        "query": query,
        "platforms": platforms or [],
        "max_per_platform": max_per_platform,
        "time_range": time_range,
        "items": [],
        "total": 0,
        "by_platform": {},
        "status": "not_implemented",
        "message": msg,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={
            "type": "search_stream",
            "data": data,
            "streamable": False,  # P1 关闭流式，等 P2 SSE
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# F2. list_search_history
# ───────────────────────────────────────────────────────────────
@tool(
    name="list_search_history",
    description="列出当前用户最近的全网搜索历史（按时间倒序，最多 50 条）。无参数。",
    parameters=None,
    group="search",
)
@with_owner
def list_search_history_tool(_owner_id: str) -> str:
    items = list_history(_owner_id)
    return ToolResult(
        success=True,
        data=items,
        ui={"type": "search_history_list", "data": {"items": items, "count": len(items)}},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# F3. clear_search_cache
# ───────────────────────────────────────────────────────────────
@tool(
    name="clear_search_cache",
    description="清空当前用户的全网搜索历史缓存。无参数。",
    parameters=None,
    group="search",
)
@with_owner
def clear_search_cache_tool(_owner_id: str) -> str:
    n = clear_history(_owner_id)
    return ToolResult(
        success=True,
        data={"cleared_count": n},
        ui={"type": "ack_text", "data": {"message": f"已清空 {n} 条搜索历史", "level": "info"}},
    ).to_json()
