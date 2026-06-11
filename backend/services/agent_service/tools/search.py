"""
F 组 全网搜索（3 个工具）

F1. web_search ⭐ streamable
    P8 实现：async generator 通过 yield 逐条推 partial，
    DirectAdapter 自动转成 on_progress 发送 tool_progress SSE。
F2. list_search_history
F3. clear_search_cache
"""
from __future__ import annotations

from typing import Optional

from core.logger import get_logger

from .._search_cache import clear_history, list_history, record_search
from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.search")


# ───────────────────────────────────────────────────────────────
# F1. web_search （async generator，streamable）
# ───────────────────────────────────────────────────────────────
@tool(
    name="web_search",
    description=(
        "跨平台全网搜索（实时拉取，不入库）。"
        "和 search_alerts 区别：本工具是即时搜索；search_alerts 查库历史。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定平台（wb/xhs/bili/zhihu/dy/ks/tieba）；空 = 全平台",
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
async def web_search_tool(
    query: str,
    _owner_id: str,
    platforms: Optional[list] = None,
    max_per_platform: int = 5,
    time_range: str = "7d",
):
    """
    async generator：yield 逐条 partial → DirectAdapter 转发为 on_progress → SSE tool_progress。
    最后一个 yield 是 ToolResult JSON。
    """
    total = 0
    by_platform: dict[str, int] = {}
    items: list[dict] = []

    yield {"type": "progress", "platform": "_all", "scanned": 0, "query": query}

    try:
        from services.search_lib.crawler_adapter import quick_crawl_stream
        from services.search_lib.filter import filter_and_summarize

        async for partial in quick_crawl_stream(
            query=query,
            platforms=platforms,
            max_per_platform=max_per_platform,
        ):
            if partial["type"] == "progress":
                plat = partial["platform"]
                scanned = partial["scanned"]
                by_platform[plat] = scanned
                yield {"type": "progress", "platform": plat, "scanned": scanned}
            elif partial["type"] == "item":
                post = partial["item"]
                try:
                    filtered = await filter_and_summarize(post, query)
                    if filtered:
                        total += 1
                        items.append(filtered)
                        yield {"type": "item", "item": filtered}
                except Exception as e:
                    logger.error(f"[web_search] filter error: {e}")
                    # 放行不过滤
                    total += 1
                    items.append({
                        "title": post.get("title", ""),
                        "snippet": (post.get("content", "") or "")[:120],
                        "url": post.get("url", ""),
                        "platform": post.get("platform", ""),
                        "relevance": 0.5,
                    })
                    yield {"type": "item", "item": items[-1]}
    except Exception as e:
        logger.error(f"[web_search] crawler error: {e}")
        # 爬虫失败时返回空结果
        pass

    record_search(_owner_id, query, total)

    data = {
        "query": query,
        "platforms": platforms or [],
        "max_per_platform": max_per_platform,
        "time_range": time_range,
        "items": items,
        "total": total,
        "by_platform": by_platform,
    }

    yield ToolResult(
        success=True,
        data=data,
        ui={"type": "search_stream", "data": data, "streamable": False},
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
