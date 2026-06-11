"""
G 组（系统状态）。

P1.2 阶段：先把旧 tools.py 里的 2 个工具（get_system_status /
get_recent_alerts）原样迁过来，验证 @tool 装饰器骨架可用。

P1.4 阶段：trigger_background_crawl 已废弃并移除，扫描入口统一由
scan.trigger_scan（带 mode + owner 隔离）提供。

P1.8 阶段：追加 get_system_overview / get_recent_activity / health_check
三个 per-user 视角的 G 组工具。
"""
from __future__ import annotations

from core.database import get_db_connection
from core.logger import get_logger

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.system")


# ───────────────────────────────────────────────────────────────
# 1) get_system_status — 雷达运行状态（v2.2 per-user 隔离）
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_system_status",
    description="获取当前用户的舆情雷达运行状态（是否正在抓取、上次抓取时间等）。无参数。",
    parameters=None,
    group="system",
)
@with_owner
def get_system_status(_owner_id: str) -> str:
    # 延迟 import 避免模块循环
    from services.radar_service.main import get_radar_status

    try:
        status = get_radar_status(owner_id=_owner_id)
        data = status.get_status_dict()
        return json.dumps(
            {"success": True, "data": data, "error": "", "error_type": ""},
            ensure_ascii=False,
        )
    except Exception as e:  # pragma: no cover
        return json.dumps(
            {"success": False, "data": None, "error": str(e), "error_type": "unknown"},
            ensure_ascii=False,
        )


# ───────────────────────────────────────────────────────────────
# 2) get_recent_alerts — 高危预警历史（旧 tool 迁入）
#    P1.5 升级为正式 search_alerts(filter=...)
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_recent_alerts",
    description=(
        "获取数据库中最近的高危（风险等级>=3）舆情警报列表。"
        "当用户询问'最近有什么负面舆情'或'历史高危事件'时使用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "要获取的记录条数，默认5"}
        },
    },
    group="system",
)
@with_owner
def get_recent_alerts(limit: int = 5, _owner_id: str = "") -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT title, platform, keyword, risk_level, core_issue, report, publish_time
                FROM ai_results
                WHERE CAST(risk_level AS INTEGER) >= 3
                  AND (owner_id = ? OR owner_id IS NULL)
                ORDER BY create_time DESC
                LIMIT ?
                """,
                (_owner_id, limit),
            )
            rows = cursor.fetchall()

        if not rows:
            return ToolResult(
                success=True,
                data={"items": [], "total": 0},
                ui={"type": "alert_list", "data": {"items": [], "total": 0}},
            ).to_json()

        results = [
            {
                "title": r[0], "platform": r[1], "keyword": r[2],
                "risk_level": r[3], "core_issue": r[4], "report": r[5], "time": r[6],
            }
            for r in rows
        ]
        return ToolResult(
            success=True,
            data={"items": results, "total": len(results)},
            ui={"type": "alert_list", "data": {"items": results, "total": len(results)}},
        ).to_json()
    except Exception as e:
        logger.error(f"[get_recent_alerts] DB Error: {e}")
        return ToolResult(
            success=False, data=None, error=f"查询失败: {e}", error_type="db_error",
        ).to_json()


# ===============================================================
# P1.8 — G 组（per-user 系统状态）
# G 组：per-user 系统状态
# ===============================================================


# ───────────────────────────────────────────────────────────────
# G1. get_system_overview — 综合快照
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_system_overview",
    description=(
        "一次性获取当前用户的全局总览（雷达状态 + 调度器 + 今日新增数据 + "
        "推送通道健康 + LLM 模型健康）。用户问'系统怎么样'、'我这边一切正常吗'时调用。"
    ),
    parameters=None,
    group="system",
)
@with_owner
def get_system_overview_tool(_owner_id: str) -> str:
    from datetime import datetime

    from core.model_config_db import AGENT_ROLES, get_effective_config
    from core.subscription_db import count_subscriptions
    from services.radar_service.db_manager import get_all_push_configs
    from services.radar_service.main import radar_status

    # 雷达
    radar = radar_status.get_status_dict() if radar_status else {}

    # 调度器（apscheduler 可选依赖；缺则置空）
    try:
        from services.radar_service.scheduler import scheduler_status
        sched = scheduler_status()
    except Exception as e:
        sched = {"active": False, "error": f"scheduler unavailable: {e}"}

    # 今日数据（按 owner_id 过滤）
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*),
                   SUM(CASE WHEN CAST(risk_level AS INTEGER) >= 3 THEN 1 ELSE 0 END)
            FROM ai_results
            WHERE (owner_id = ? OR owner_id IS NULL)
              AND DATE(create_time) = ?
            """,
            (_owner_id, today),
        )
        row = cur.fetchone()
        total_today = int(row[0] or 0)
        high_risk_today = int(row[1] or 0)

    # 订阅数
    sub_count = count_subscriptions(_owner_id)

    # 推送通道健康
    push_cfgs = get_all_push_configs(owner_id=_owner_id)
    channels_health = []
    for ch in ("email", "wecom", "feishu"):
        c = push_cfgs.get(ch) or {}
        channels_health.append({
            "channel": ch,
            "enabled": bool(c.get("enabled", False)),
        })

    # LLM 模型健康（不调用，只看是否配置好）
    llm_health = []
    for role in AGENT_ROLES:
        eff = get_effective_config(_owner_id, role)
        llm_health.append({
            "agent_role": role,
            "configured": bool(eff.get("api_key") and eff.get("model")),
            "is_user_override": eff.get("is_user_override", False),
        })

    data = {
        "radar": radar,
        "scheduler": sched,
        "today_stats": {
            "date": today,
            "total_alerts": total_today,
            "high_risk_alerts": high_risk_today,
            "subscription_count": sub_count,
        },
        "channels_health": channels_health,
        "llm_health": llm_health,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "system_overview", "data": data},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# G2. get_recent_activity — 近 N 分钟活动
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_recent_activity",
    description=(
        "查询当前用户最近 N 分钟的活动（新预警、爬虫执行、推送记录、Agent 决策）。"
        "默认 60 分钟。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "minutes": {
                "type": "integer",
                "minimum": 5,
                "maximum": 1440,
                "description": "查询窗口（分钟），默认 60",
            },
        },
    },
    group="system",
)
@with_owner
def get_recent_activity_tool(_owner_id: str, minutes: int = 60) -> str:
    from datetime import datetime, timedelta

    from services.radar_service.db_manager import get_audit_log

    if minutes < 5:
        minutes = 5
    if minutes > 1440:
        minutes = 1440
    since = (datetime.now() - timedelta(minutes=minutes)).isoformat()

    events: list[dict] = []

    # 1) 新预警（per-owner）
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT post_id, title, platform, keyword, risk_level, create_time
            FROM ai_results
            WHERE (owner_id = ? OR owner_id IS NULL)
              AND create_time >= ?
            ORDER BY create_time DESC
            LIMIT 100
            """,
            (_owner_id, since),
        )
        for r in cur.fetchall():
            events.append({
                "type": "alert",
                "time": r[5],
                "title": r[1],
                "platform": r[2],
                "keyword": r[3],
                "risk_level": r[4],
            })

    # 2) 审计日志（v2.2 per-owner 过滤）
    try:
        for log in get_audit_log(limit=50, owner_id=_owner_id):
            t = log.get("created_at")
            if t and t < since:
                continue
            events.append({
                "type": "audit",
                "time": t,
                "action": log.get("action"),
                "keyword": log.get("keyword"),
                "level": log.get("level"),
                "detail": log.get("detail"),
            })
    except Exception as e:
        logger.warning(f"[get_recent_activity] audit_log 读取失败: {e}")

    # 时间倒序
    events.sort(key=lambda x: x.get("time") or "", reverse=True)
    events = events[:50]

    data = {
        "minutes": minutes,
        "count": len(events),
        "events": events,
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "activity_timeline", "data": data},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# G3. health_check — 组件健康
# ───────────────────────────────────────────────────────────────
@tool(
    name="health_check",
    description="健康检查：数据库 / 调度器 / 推送通道 / LLM 模型。返回组件健康灯列表。",
    parameters=None,
    group="system",
)
@with_owner
def health_check_tool(_owner_id: str) -> str:
    from core.model_config_db import AGENT_ROLES, get_effective_config
    from services.radar_service.db_manager import get_all_push_configs

    components = []

    # 1) DB
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        components.append({"name": "database", "status": "ok", "detail": "SQLite 可读"})
    except Exception as e:
        components.append({"name": "database", "status": "error", "detail": str(e)})

    # 2) Scheduler（apscheduler 可选）
    try:
        from services.radar_service.scheduler import scheduler_status
        s = scheduler_status()
        components.append({
            "name": "scheduler",
            "status": "ok" if s.get("active") else "warning",
            "detail": (
                f"active={s.get('active')} next={s.get('next_run_time')} "
                f"interval_h={s.get('interval_hours')}"
            ),
        })
    except Exception as e:
        components.append({"name": "scheduler", "status": "warning", "detail": f"unavailable: {e}"})

    # 3) Push channels
    try:
        cfgs = get_all_push_configs(owner_id=_owner_id)
        enabled = [ch for ch in ("email", "wecom", "feishu") if (cfgs.get(ch) or {}).get("enabled")]
        components.append({
            "name": "push_channels",
            "status": "ok" if enabled else "warning",
            "detail": f"启用通道: {enabled or '无'}",
        })
    except Exception as e:
        components.append({"name": "push_channels", "status": "error", "detail": str(e)})

    # 4) LLM 模型
    try:
        missing = []
        for role in AGENT_ROLES:
            eff = get_effective_config(_owner_id, role)
            if not (eff.get("api_key") and eff.get("model")):
                missing.append(role)
        components.append({
            "name": "llm_models",
            "status": "warning" if missing else "ok",
            "detail": f"缺失角色: {missing}" if missing else "全部角色已配置",
        })
    except Exception as e:
        components.append({"name": "llm_models", "status": "error", "detail": str(e)})

    overall = "ok"
    if any(c["status"] == "error" for c in components):
        overall = "error"
    elif any(c["status"] == "warning" for c in components):
        overall = "warning"

    data = {"overall": overall, "components": components}
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "health_grid", "data": data},
    ).to_json()
