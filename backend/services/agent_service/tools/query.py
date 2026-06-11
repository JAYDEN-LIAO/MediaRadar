"""
C 组 数据查询（3 个工具，检索预警/话题详情/搜索）

C1. search_alerts：检索历史预警/动态（ai_results + topic_summary 双表）
C2. get_topic_detail：话题详情（聚合 + 帖子列表）
C3. get_subscription_stats：订阅维度统计（话题数、热度、平台分布、推送命中率）

P1 限制：topic_summary 表 P6 才会全量铺开，所以 C1 优先查 ai_results；
C3 的 push_stats 暂只统计计数，命中率/压制率等 P7 加入。
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from core.database import get_db_connection
from core.logger import get_logger
from core.subscription_db import get_subscription_by_id
from services.radar_service.db_manager import (
    get_latest_results,
    get_topic_posts,
    get_topic_summary_by_id,
    get_topic_summary_list,
)

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.query")


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# L4 v2.2: 搜索关键词清洗
# - 剥离前后空白
# - 截断到 64 字符
# - 移除控制字符（防日志注入 / 终端欺骗）
# - 移除 SQL/Shell 注入常见元字符（? 已是参数化，再保险一层）
_KEYWORD_MAX_LEN = 64
_BAD_CTRL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_keyword(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = _BAD_CTRL_CHARS.sub("", s)
    if len(s) > _KEYWORD_MAX_LEN:
        s = s[:_KEYWORD_MAX_LEN]
    return s or None


# ───────────────────────────────────────────────────────────────
# C1. search_alerts
# ───────────────────────────────────────────────────────────────
@tool(
    name="search_alerts",
    description=(
        "按关键词/平台/风险等级/时间范围检索历史数据。"
        "用户问'最近小米/华为的动态'、'上周的高危预警'、'微博上有什么'时调用。"
        "type=alert 只查预警，type=dynamic 只查话题动态，type=all 全部。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "订阅名/关键词，模糊匹配"},
            "platform": {
                "type": "string",
                "enum": ["weibo", "xhs", "douyin", "bilibili", "zhihu", "tieba", "kuaishou", "wb", "dy", "bili", "ks"],
            },
            "risk_level_min": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "最低风险等级，1=安全 5=高危。默认 1",
            },
            "type": {
                "type": "string",
                "enum": ["dynamic", "alert", "all"],
                "description": "返回类型：dynamic=话题动态、alert=预警、all=两者。默认 all",
            },
            "start_time": {"type": "string", "description": "ISO8601 起始时间，例 '2026-06-01T00:00:00'"},
            "end_time": {"type": "string", "description": "ISO8601 结束时间"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "返回条数上限，默认 10"},
        },
    },
    group="query",
)
@with_owner
def search_alerts_tool(
    _owner_id: str,
    keyword: Optional[str] = None,
    platform: Optional[str] = None,
    risk_level_min: int = 1,
    type: str = "all",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 10,
) -> str:
    # L4 v2.2: 关键词清洗
    keyword = _sanitize_keyword(keyword)
    # 限制 limit 上限（即便 schema 限定 50，再加一道程序保护）
    if limit <= 0 or limit > 50:
        limit = 10
    start_dt = _parse_iso(start_time)
    end_dt = _parse_iso(end_time)
    # 平台别名归一
    platform_alias = {
        "weibo": "微博", "wb": "微博",
        "xhs": "小红书",
        "douyin": "抖音", "dy": "抖音",
        "bilibili": "B站", "bili": "B站",
        "zhihu": "知乎",
        "tieba": "贴吧",
        "kuaishou": "快手", "ks": "快手",
    }
    platform_cn = platform_alias.get(platform) if platform else None

    items: list[dict] = []

    # ── 预警分支 (ai_results)
    if type in ("alert", "all"):
        raw = get_latest_results(limit=200, owner_id=_owner_id)
        for r in raw:
            try:
                risk = int(r.get("risk_level") or 0)
            except (TypeError, ValueError):
                risk = 0
            if risk < risk_level_min:
                continue
            if keyword and keyword not in (r.get("keyword") or ""):
                continue
            if platform_cn and platform_cn not in (r.get("platform") or ""):
                continue
            t = _parse_iso(r.get("publish_time")) or _parse_iso(r.get("create_time"))
            if start_dt and t and t < start_dt:
                continue
            if end_dt and t and t > end_dt:
                continue
            items.append({
                "kind": "alert",
                "id": r.get("post_id"),
                "title": r.get("title"),
                "platform": r.get("platform"),
                "keyword": r.get("keyword"),
                "risk_level": r.get("risk_level"),
                "core_issue": r.get("core_issue"),
                "report": r.get("report"),
                "time": r.get("publish_time") or r.get("create_time"),
            })

    # ── 动态分支 (topic_summary)
    if type in ("dynamic", "all"):
        topics = get_topic_summary_list(
            keyword=keyword,
            platform=platform,
            owner_id=_owner_id,
            limit=200,
        )
        for t in topics:
            ts = _parse_iso(t.get("last_seen")) or _parse_iso(t.get("first_seen"))
            if start_dt and ts and ts < start_dt:
                continue
            if end_dt and ts and ts > end_dt:
                continue
            items.append({
                "kind": "dynamic",
                "id": t.get("topic_id"),
                "title": t.get("topic_name"),
                "platform": "+".join(t.get("platforms", [])) or "—",
                "keyword": t.get("keyword"),
                "risk_level": t.get("risk_level"),
                "sentiment": t.get("sentiment"),
                "post_count": t.get("post_count"),
                "core_issue": t.get("core_issue"),
                "time": t.get("last_seen") or t.get("first_seen"),
            })

    # 按时间倒序 + 截断
    items.sort(key=lambda x: x.get("time") or "", reverse=True)
    items = items[:limit]

    return ToolResult(
        success=True,
        data=items,
        ui={
            "type": "alert_list",
            "data": {
                "items": items,
                "count": len(items),
                "filter": {
                    "keyword": keyword,
                    "platform": platform,
                    "risk_level_min": risk_level_min,
                    "type": type,
                },
            },
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# C2. get_topic_detail
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_topic_detail",
    description="查询某话题的完整详情（摘要 + 所有相关帖子 + Agent 总结）。",
    parameters={
        "type": "object",
        "properties": {
            "topic_id": {"type": "string"},
        },
        "required": ["topic_id"],
    },
    group="query",
)
@with_owner
def get_topic_detail_tool(topic_id: str, _owner_id: str) -> str:
    topic = get_topic_summary_by_id(topic_id, owner_id=_owner_id)
    if not topic:
        return ToolResult(
            success=False,
            error=f"话题不存在或无权限: {topic_id}",
            error_type="not_found",
        ).to_json()

    posts = get_topic_posts(topic_id, owner_id=_owner_id)
    data = {**topic, "posts": posts, "post_count": len(posts)}
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "topic_card", "data": data},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# C3. get_subscription_stats
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_subscription_stats",
    description=(
        "查询某订阅在最近 N 天的统计（话题数、平台分布、风险分布、热度趋势）。"
        "用户问'小米最近怎么样'、'近 7 天的数据'时调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "subscription_id": {"type": "string"},
            "days": {"type": "integer", "minimum": 1, "maximum": 30, "description": "统计窗口（天），默认 7"},
        },
        "required": ["subscription_id"],
    },
    group="query",
)
@with_owner
def get_subscription_stats_tool(subscription_id: str, _owner_id: str, days: int = 7) -> str:
    sub = get_subscription_by_id(_owner_id, subscription_id)
    if not sub:
        return ToolResult(
            success=False,
            error=f"订阅不存在或无权限: {subscription_id}",
            error_type="not_found",
        ).to_json()

    keyword = sub["name"]
    since = (datetime.now() - timedelta(days=days)).isoformat()

    # 直接查 ai_results（topic_summary 等 P6）
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT platform, risk_level, sentiment, publish_time, create_time
            FROM ai_results
            WHERE (owner_id = ? OR owner_id IS NULL)
              AND keyword = ?
              AND (publish_time >= ? OR create_time >= ?)
            ORDER BY create_time DESC
            """,
            (_owner_id, keyword, since, since),
        )
        rows = [dict(r) for r in cursor.fetchall()]

    platform_dist = Counter(r.get("platform") or "未知" for r in rows)
    risk_dist = Counter(str(r.get("risk_level") or "0") for r in rows)
    sentiment_dist = Counter(r.get("sentiment") or "Neutral" for r in rows)

    # 按天分桶（trend）
    daily = defaultdict(int)
    for r in rows:
        t = _parse_iso(r.get("publish_time")) or _parse_iso(r.get("create_time"))
        if not t:
            continue
        daily[t.date().isoformat()] += 1
    trend = [{"date": d, "count": c} for d, c in sorted(daily.items())]

    data = {
        "subscription_id": subscription_id,
        "name": keyword,
        "days": days,
        "total_posts": len(rows),
        "platform_dist": dict(platform_dist),
        "risk_dist": dict(risk_dist),
        "sentiment_dist": dict(sentiment_dist),
        "trend": trend,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "stats_chart", "data": data},
    ).to_json()
