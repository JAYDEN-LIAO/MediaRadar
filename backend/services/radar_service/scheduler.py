# backend/services/radar_service/scheduler.py
"""
APScheduler 定时调度模块

- 每天从 start_time 开始，按 monitor_frequency 间隔执行雷达扫描
- 全局锁防止并发扫描
- FastAPI on_event 启动/停止调度器
"""
import asyncio
import datetime
import threading
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.logger import get_logger

logger = get_logger("radar.scheduler")

# ---- 全局状态 ----
_scheduler: Optional[BackgroundScheduler] = None
_scan_lock: asyncio.Lock = asyncio.Lock()
_is_running: bool = False


def _get_scan_job_id() -> str:
    return "radar_scheduled_scan"


def _build_trigger(start_time: str, monitor_frequency: float):
    """
    构建 APScheduler trigger：
    - 每天在 start_time 执行第一次
    - 之后按 monitor_frequency 小时间隔重复
    - IntervalTrigger 支持所有频率（< 1h / >= 1h / 24h 全部适用）
    """
    hour, minute = map(int, start_time.split(":"))
    start_date = datetime.datetime.today().replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return IntervalTrigger(
        hours=monitor_frequency,
        start_date=start_date,
    )


def _run_scan():
    """定时任务执行函数（运行在线程中，需创建独立事件循环）"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if not _scan_lock.locked():
                # 用临时事件循环运行异步任务
                async def _run():
                    async with _scan_lock:
                        logger.info("[Scheduler] 开始执行定时雷达扫描...")
                        try:
                            from .main import job_async
                            await job_async()
                            logger.info("[Scheduler] 定时雷达扫描完成")
                        except Exception as e:
                            logger.error(f"[Scheduler] 定时雷达扫描异常: {e}")
                loop.run_until_complete(_run())
            else:
                logger.warning("[Scheduler] 扫描进行中，跳过本次触发")
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"[Scheduler] 扫描线程异常: {e}")


def scheduler_start() -> tuple[bool, str]:
    """启动调度器，从数据库读取 start_time + monitor_frequency"""
    global _scheduler, _is_running

    if _is_running and _scheduler is not None:
        return True, "调度器已在运行中"

    try:
        from .db_manager import get_system_settings
        conf = get_system_settings()
    except Exception as e:
        logger.error(f"[Scheduler] 无法读取系统配置: {e}")
        return False, f"读取配置失败: {e}"

    start_time = conf.get("start_time", "08:00")
    monitor_frequency = float(conf.get("monitor_frequency", 1.0))

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    trigger = _build_trigger(start_time, monitor_frequency)

    _scheduler.add_job(
        _run_scan,
        trigger=trigger,
        id=_get_scan_job_id(),
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.start()
    _is_running = True

    # 注册每日简报任务
    _schedule_daily_summary()

    logger.info(f"[Scheduler] 调度器已启动: start_time={start_time}, frequency={monitor_frequency}h")
    job = _scheduler.get_job(_get_scan_job_id())
    next_str = job.next_run_time.isoformat() if job and job.next_run_time else "未知"
    return True, f"调度器已启动，下次执行: {next_str}"


def scheduler_stop() -> tuple[bool, str]:
    """停止调度器"""
    global _scheduler, _is_running

    if _scheduler is None:
        return True, "调度器未运行"

    _scheduler.shutdown(wait=False)
    _is_running = False
    _scheduler = None
    logger.info("[Scheduler] 调度器已停止")
    return True, "调度器已停止"


def scheduler_status() -> dict:
    """返回调度器当前状态"""
    global _scheduler, _is_running

    if not _is_running or _scheduler is None:
        return {
            "active": False,
            "next_run": None,
            "interval_hours": None,
            "start_time": None,
            "scan_in_progress": _scan_lock.locked(),
        }

    job = _scheduler.get_job(_get_scan_job_id())
    next_run_time = None
    if job and job.next_run_time:
        next_run_time = job.next_run_time.isoformat()

    try:
        from .db_manager import get_system_settings
        conf = get_system_settings()
        monitor_frequency = float(conf.get("monitor_frequency", 1.0))
        start_time = conf.get("start_time", "08:00")
    except Exception:
        monitor_frequency = None
        start_time = None

    return {
        "active": True,
        "next_run": next_run_time,
        "interval_hours": monitor_frequency,
        "start_time": start_time,
        "scan_in_progress": _scan_lock.locked(),
    }


def reschedule_if_running(start_time: str, monitor_frequency: float) -> bool:
    """
    当系统配置变更时，重新调度已存在的任务。
    仅当调度器运行时调用。monitor_frequency < 0 时仅暂停扫描任务，不影响每日简报。
    """
    global _scheduler, _is_running

    if not _is_running or _scheduler is None:
        return False

    if monitor_frequency < 0:
        # 仅暂停扫描任务，保持调度器继续运行（每日简报不受影响）
        job = _scheduler.get_job(_get_scan_job_id())
        if job:
            _scheduler.remove_job(_get_scan_job_id())
            logger.info("[Scheduler] 扫描任务已暂停（频率为-1），每日简报继续运行")
        return True

    trigger = _build_trigger(start_time, monitor_frequency)
    job = _scheduler.get_job(_get_scan_job_id())

    if job:
        job.reschedule(trigger)
        logger.info(f"[Scheduler] 任务已重新调度: start_time={start_time}, frequency={monitor_frequency}h")
    else:
        _scheduler.add_job(
            _run_scan,
            trigger=trigger,
            id=_get_scan_job_id(),
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info(f"[Scheduler] 新任务已添加: start_time={start_time}, frequency={monitor_frequency}h")

    return True


# ---- 每日简报任务 ----

def _get_summary_job_id() -> str:
    return "daily_summary_job"


def _run_daily_summary():
    """每日简报任务（运行在线程中）"""
    try:
        from .db_manager import get_system_settings
        conf = get_system_settings()

        if not conf.get("push_summary", False):
            logger.info("[Scheduler] 每日简报开关未开启，跳过")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _run():
                logger.info("[Scheduler] 开始生成每日简报...")
                try:
                    from .push_generator import generate_daily_summary_html
                    html = await generate_daily_summary_html()
                    if not html:
                        logger.info("[Scheduler] 今日无新舆情，简报不发送")
                        return
                    from .notifier import send_alert
                    send_alert(
                        keyword="舆情监测",
                        platform="全部平台",
                        risk_level=2,
                        risk_class="medium",
                        core_issue="每日舆情监测简报",
                        report="今日舆情概况已生成，请查收邮件。",
                        urls=[],
                        email_html=html,
                    )
                    logger.info("[Scheduler] 每日简报发送成功")
                except Exception as e:
                    logger.error(f"[Scheduler] 每日简报异常: {e}")
            loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"[Scheduler] 每日简报线程异常: {e}")


def _schedule_daily_summary():
    """注册每日简报任务（push_time 触发）"""
    global _scheduler
    if _scheduler is None:
        return

    try:
        from .db_manager import get_system_settings
        conf = get_system_settings()
    except Exception:
        return

    if not conf.get("push_summary", False):
        logger.info("[Scheduler] 每日简报未启用，不注册任务")
        return

    push_time = conf.get("push_time", "18:00")
    hour, minute = map(int, push_time.split(":"))

    old_job = _scheduler.get_job(_get_summary_job_id())
    if old_job:
        _scheduler.remove_job(_get_summary_job_id())

    trigger = CronTrigger(hour=hour, minute=minute, second=0, timezone="Asia/Shanghai")
    _scheduler.add_job(
        _run_daily_summary,
        trigger=trigger,
        id=_get_summary_job_id(),
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(f"[Scheduler] 每日简报任务已注册: {push_time}")


def reschedule_daily_summary_if_running() -> bool:
    """当 push_summary / push_time 变更时，重新调度简报任务"""
    global _scheduler, _is_running
    if not _is_running or _scheduler is None:
        return False
    _schedule_daily_summary()
    return True
