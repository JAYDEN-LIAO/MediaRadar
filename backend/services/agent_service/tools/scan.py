"""
B 组 扫描 / 调度（5 个工具，AGENT_REDESIGN.md §4.B 落 P1 版本）

P1 限制：底层调度器仍是全局单例，per-user 调度要等 P6 完成 Pipeline
重构后才能拆开。因此本组工具：
- 写入操作（trigger_scan / set_scan_interval / pause / resume）会影响全局调度
- 状态读取 (get_scan_status / get_next_run_time) 返回全局状态
- 文档/UI 上要告知用户"P1 暂时是全局调度，不区分用户"

到了 P6：每个用户独立 schedule，底层按关键词合并去重。
"""
from __future__ import annotations

import json
from typing import Optional

from core.logger import get_logger

from ._base import ToolResult, tool
from ._owner import with_owner

logger = get_logger("agent.tools.scan")


# ───────────────────────────────────────────────────────────────
# B1. trigger_scan — 立即触发一次扫描
# ───────────────────────────────────────────────────────────────
@tool(
    name="trigger_scan",
    description=(
        "立即触发一次扫描（异步后台执行）。"
        "用户说'现在扫一下/抓最新/帮我看看新动态'时调用。"
        "调完此工具后**不要**再调任何其他工具，直接告诉用户任务已在后台跑。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["full", "trending", "fan_track", "quick_search"],
                "description": "扫描模式。P1 仅 full 完整生效；其他 mode 占位等 P6。默认 trending",
            },
            "subscription_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "只扫指定订阅；空数组 = 扫当前用户全部订阅。P1 不支持，留 P6",
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定平台；空 = 全平台",
            },
        },
    },
    group="scan",
)
@with_owner
def trigger_scan_tool(
    _owner_id: str,
    mode: str = "trending",
    subscription_ids: Optional[list] = None,
    platforms: Optional[list] = None,
) -> str:
    """复用现有 job() + asyncio.create_task；owner_id 透传给底层 pipeline。"""
    import asyncio
    import time
    import traceback
    from services.radar_service.main import job, radar_status, MONITOR_KEYWORDS

    if radar_status.is_running:
        return ToolResult(
            success=True,
            data={
                "status": "already_running",
                "message": "扫描任务已经在跑了，等当前一轮结束再触发吧。",
                "started_at": getattr(radar_status, "started_at", None),
            },
            ui={
                "type": "scan_progress",
                "data": {"status": "already_running"},
            },
        ).to_json()

    keyword_summary = "、".join(MONITOR_KEYWORDS) if MONITOR_KEYWORDS else "全局词库"

    async def _run():
        try:
            radar_status.set_running_sync(f"Agent 触发: mode={mode} owner={_owner_id}")
            loop = asyncio.get_running_loop()
            # job() 第 2 参数支持 owner_id（main.py:342）
            new_count = await loop.run_in_executor(
                None, lambda: job(None, _owner_id)
            )
            if new_count is not None:
                radar_status.set_result_sync(
                    new_count, time.strftime("%Y-%m-%d %H:%M:%S")
                )
        except Exception as e:
            logger.error(f"[trigger_scan] {e}\n{traceback.format_exc()}")
        finally:
            radar_status.set_idle_sync()

    try:
        asyncio.create_task(_run())
    except RuntimeError:
        import threading

        threading.Thread(target=lambda: job(None, _owner_id), daemon=True).start()

    return ToolResult(
        success=True,
        data={
            "status": "started",
            "mode": mode,
            "owner_id": _owner_id,
            "keyword_summary": keyword_summary,
            "message": "扫描任务已下达，后台执行中。",
        },
        ui={
            "type": "scan_progress",
            "data": {"status": "started", "mode": mode},
            "streamable": False,  # P1 不流式；P2 SSE 升级后改 true
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# B2. get_scan_status
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_scan_status",
    description="查询雷达当前的扫描状态（是否运行中、上次完成时间、本轮已抓多少新内容）。",
    parameters=None,
    group="scan",
)
@with_owner
def get_scan_status_tool(_owner_id: str) -> str:
    from services.radar_service.main import radar_status

    data = radar_status.get_status_dict()
    # P1 全局状态，per-user 视图等 P6
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "scan_status", "data": data},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# B3. set_scan_interval
# ───────────────────────────────────────────────────────────────
@tool(
    name="set_scan_interval",
    description="修改全局扫描频率（P1 全局生效；P6 改 per-user）。单位：分钟。",
    parameters={
        "type": "object",
        "properties": {
            "interval_min": {
                "type": "integer",
                "minimum": 5,
                "maximum": 1440,
                "description": "扫描间隔（分钟），范围 5~1440",
            },
        },
        "required": ["interval_min"],
    },
    group="scan",
)
@with_owner
def set_scan_interval_tool(interval_min: int, _owner_id: str) -> str:
    """改 system_settings.monitor_frequency（小时数）+ 重新调度。"""
    if interval_min < 5 or interval_min > 1440:
        return ToolResult(
            success=False,
            error="interval_min 必须在 5~1440 之间",
            error_type="validation",
        ).to_json()

    from services.radar_service.db_manager import (
        get_system_settings,
        save_system_settings,
    )
    from services.radar_service.scheduler import reschedule_if_running

    conf = get_system_settings()
    old_interval = float(conf.get("monitor_frequency", 1.0)) * 60  # 小时 → 分钟
    new_freq_hours = interval_min / 60.0
    conf["monitor_frequency"] = new_freq_hours
    save_system_settings(conf)

    reschedule_if_running(conf.get("start_time", "08:00"), new_freq_hours)

    return ToolResult(
        success=True,
        data={
            "old_interval_min": old_interval,
            "new_interval_min": interval_min,
            "next_run_at": None,  # B5 单独查
        },
        ui={
            "type": "scheduler_info",
            "data": {"interval_min": interval_min, "changed": True},
        },
    ).to_json()


# ───────────────────────────────────────────────────────────────
# B4a/B4b. pause_scheduler / resume_scheduler
# ───────────────────────────────────────────────────────────────
@tool(
    name="pause_scheduler",
    description="暂停定时扫描（不影响手动 trigger_scan）。",
    parameters=None,
    group="scan",
)
@with_owner
def pause_scheduler_tool(_owner_id: str) -> str:
    from services.radar_service.scheduler import scheduler_stop

    ok, msg = scheduler_stop()
    return ToolResult(
        success=ok,
        data={"active": False, "message": msg},
        error="" if ok else msg,
        ui={"type": "scheduler_info", "data": {"active": False}},
    ).to_json()


@tool(
    name="resume_scheduler",
    description="恢复定时扫描。",
    parameters=None,
    group="scan",
)
@with_owner
def resume_scheduler_tool(_owner_id: str) -> str:
    from services.radar_service.scheduler import scheduler_start

    ok, msg = scheduler_start()
    return ToolResult(
        success=ok,
        data={"active": ok, "message": msg},
        error="" if ok else msg,
        ui={"type": "scheduler_info", "data": {"active": ok}},
    ).to_json()


# ───────────────────────────────────────────────────────────────
# B5. get_next_run_time
# ───────────────────────────────────────────────────────────────
@tool(
    name="get_next_run_time",
    description="查询下次扫描时间 + 当前频率 + 调度器是否激活。",
    parameters=None,
    group="scan",
)
@with_owner
def get_next_run_time_tool(_owner_id: str) -> str:
    try:
        from services.radar_service.scheduler import scheduler_status
        status = scheduler_status()
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"scheduler unavailable: {e}",
            error_type="dependency_missing",
            ui={"type": "scheduler_info", "data": {"active": False, "error": str(e)}},
        ).to_json()

    interval_hours = status.get("interval_hours")
    interval_min = int(interval_hours * 60) if interval_hours else None
    data = {
        "next_run_at": status.get("next_run_time"),
        "interval_min": interval_min,
        "active": status.get("active", False),
        "scan_in_progress": status.get("scan_in_progress", False),
    }
    return ToolResult(
        success=True,
        data=data,
        ui={"type": "scheduler_info", "data": data},
    ).to_json()
