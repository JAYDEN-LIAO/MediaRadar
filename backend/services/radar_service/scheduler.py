# backend/services/radar_service/scheduler.py
"""
APScheduler 定时调度模块（v2.2 per-user 版本）

架构：
  - 全局 BackgroundScheduler 管理所有 job
  - 一个全局扫描任务（每 monitor_frequency 小时执行），但会遍历所有有订阅的用户
  - 一个全局每日简报任务
  - 底层合并关键词：从所有用户的 subscription 表收集关键词，全局爬 1 轮，
    然后按 owner 拆分跑 Pipeline

全局锁：
  - _scan_lock: 全局唯一扫描锁，防止多用户并发扫描（爬虫会抢资源）
  - 锁被持有时，新触发的任务直接跳过
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

# v2.2: per-user 最后扫描时间，用于决定本轮是否需要为某用户跑扫描
_user_last_scan_at: dict[str, datetime.datetime] = {}
_user_last_scan_lock: threading.Lock = threading.Lock()


def _should_user_scan_now(owner_id: str, interval_min: float) -> bool:
    """根据 per-user 间隔判断是否该执行扫描。interval_min<=0 视为已暂停。"""
    if interval_min <= 0:
        return False
    with _user_last_scan_lock:
        last = _user_last_scan_at.get(owner_id)
    if last is None:
        return True  # 首次必跑
    delta_min = (datetime.datetime.now() - last).total_seconds() / 60.0
    return delta_min >= interval_min


def _mark_user_scanned(owner_id: str) -> None:
    with _user_last_scan_lock:
        _user_last_scan_at[owner_id] = datetime.datetime.now()


def _get_scan_job_id() -> str:
    return "radar_scheduled_scan"


def _build_trigger(start_time: str, monitor_frequency: float):
    """
    构建 APScheduler trigger：
    - 每天在 start_time 执行第一次
    - 之后按 monitor_frequency 小时间隔重复
    """
    hour, minute = map(int, start_time.split(":"))
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    start_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start_date <= now:
        start_date += datetime.timedelta(days=1)
    return IntervalTrigger(
        hours=monitor_frequency,
        start_date=start_date,
        timezone="Asia/Shanghai",
    )


def _collect_users_and_keywords():
    """
    从 subscription 表收集所有非暂停用户的订阅关键词。

    Returns:
        dict[str, list[str]]: {owner_id: [keyword1, keyword2, ...]}
    """
    try:
        import sqlite3
        from core.database import get_db_connection
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT owner_id, name FROM subscription WHERE is_active = 1"
            )
            rows = cursor.fetchall()
        result: dict[str, list[str]] = {}
        for r in rows:
            oid = r["owner_id"]
            name = r["name"]
            result.setdefault(oid, []).append(name)
        return result
    except Exception as e:
        logger.warning(f"[Scheduler] 读取 subscriptions 失败: {e}")
        return {}


def _run_scan():
    """
    定时扫描任务（v2.2 per-user 版本）。

    流程（v2.2 修订）：
      1. 收集所有活跃用户订阅
      2. 对每个用户读取 quota.scan_interval_min / scan_paused
      3. 若用户已暂停或距上次扫描未到间隔，跳过
      4. 否则为该用户跑 Pipeline（owner-scoped）
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if not _scan_lock.locked():
                async def _run():
                    async with _scan_lock:
                        logger.info("[Scheduler] 开始执行定时雷达扫描...")
                        try:
                            # 1. 收集所有活跃订阅
                            user_keywords = _collect_users_and_keywords()
                            if not user_keywords:
                                logger.info("[Scheduler] 无活跃订阅，跳过扫描")
                                return

                            # 2. 读取 per-user 扫描配置
                            from core.quota_db import get_scan_config
                            from .main import job_async

                            ready_users: list[tuple[str, list[str]]] = []
                            skipped_paused = 0
                            skipped_interval = 0

                            for oid, kws in user_keywords.items():
                                try:
                                    cfg = get_scan_config(oid)
                                except Exception as e:
                                    logger.warning(
                                        f"[Scheduler] 读取 user={oid[:8]}... scan config 失败: {e}"
                                    )
                                    cfg = {"interval_min": 60, "paused": False}
                                if cfg.get("paused"):
                                    skipped_paused += 1
                                    continue
                                interval_min = float(cfg.get("interval_min") or 60)
                                if not _should_user_scan_now(oid, interval_min):
                                    skipped_interval += 1
                                    continue
                                ready_users.append((oid, kws))

                            logger.info(
                                f"[Scheduler] 候选用户 {len(user_keywords)} 个 → "
                                f"本轮触发 {len(ready_users)}，"
                                f"暂停 {skipped_paused}，未到间隔 {skipped_interval}"
                            )

                            if not ready_users:
                                return

                            # 3. 逐用户跑扫描
                            for oid, kws in ready_users:
                                logger.info(
                                    f"[Scheduler] 为用户 {oid[:8]}... 执行扫描"
                                    f"（{len(kws)} 关键词）"
                                )
                                try:
                                    await job_async(owner_id=oid)
                                    _mark_user_scanned(oid)
                                except Exception as e:
                                    logger.error(
                                        f"[Scheduler] user={oid[:8]}... 扫描异常: {e}"
                                    )

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

    if monitor_frequency >= 0:
        trigger = _build_trigger(start_time, monitor_frequency)
        _scheduler.add_job(
            _run_scan,
            trigger=trigger,
            id=_get_scan_job_id(),
            replace_existing=True,
            misfire_grace_time=60,
        )
        freq_display = f"{monitor_frequency}h"
    else:
        freq_display = "已暂停"
        logger.info("[Scheduler] 扫描任务已暂停（频率为负值），仅运行每日简报")

    _scheduler.start()
    _is_running = True

    _schedule_daily_summary()
    _schedule_memory_cleanup()

    logger.info(f"[Scheduler] 调度器已启动: start_time={start_time}, frequency={freq_display}")
    if monitor_frequency >= 0:
        job = _scheduler.get_job(_get_scan_job_id())
        next_str = job.next_run_time.isoformat() if job and job.next_run_time else "未知"
        return True, f"调度器已启动，下次执行: {next_str}"
    else:
        return True, "调度器已启动，扫描任务已暂停（频率为负值），每日简报继续运行"


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

    # 活跃用户数
    user_count = len(_collect_users_and_keywords())

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
        "active_users": user_count,
    }


def reschedule_if_running(start_time: str, monitor_frequency: float) -> bool:
    """当系统配置变更时，重新调度已存在的任务。"""
    global _scheduler, _is_running

    if not _is_running or _scheduler is None:
        return False

    if monitor_frequency < 0:
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
    """每日简报任务（运行在线程中，per-user 分发）"""
    try:
        from .db_manager import get_system_settings
        conf = get_system_settings()

        if not conf.get("push_summary", False):
            logger.info("[Scheduler] 每日简报开关未开启，跳过")
            return

        # v2.2: 收集所有活跃订阅用户，逐一为其生成 + 推送简报
        user_keywords = _collect_users_and_keywords()
        if not user_keywords:
            logger.info("[Scheduler] 无活跃订阅用户，跳过每日简报")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _run():
                logger.info(
                    f"[Scheduler] 开始为 {len(user_keywords)} 个用户生成每日简报..."
                )
                from .push_generator import generate_daily_summary_html
                from .notifier import send_alert

                for oid in user_keywords.keys():
                    try:
                        html = await generate_daily_summary_html(owner_id=oid)
                        if not html:
                            logger.info(
                                f"[Scheduler] 用户 {oid[:8]}... 今日无新舆情，跳过"
                            )
                            continue
                        send_alert(
                            owner_id=oid,
                            keyword="舆情监测",
                            platform="全部平台",
                            risk_level=2,
                            risk_class="medium",
                            core_issue="每日舆情监测简报",
                            report="今日舆情概况已生成，请查收邮件。",
                            urls=[],
                            email_html=html,
                        )
                        logger.info(
                            f"[Scheduler] 用户 {oid[:8]}... 每日简报发送成功"
                        )
                    except Exception as e:
                        logger.error(
                            f"[Scheduler] 用户 {oid[:8]}... 每日简报异常: {e}"
                        )
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


# ---- 每日 03:00 fact_memory TTL 清理 ----

def _get_memory_cleanup_job_id() -> str:
    return "agent_memory_cleanup"


def _run_memory_cleanup():
    """每日 03:00 执行 fact_memory 过期清理"""
    try:
        from services.agent_service.memory.memory_manager import AgentMemoryManager
        mgr = AgentMemoryManager()
        deleted = mgr.cleanup_expired_memory()
        logger.info(f"[Scheduler] 记忆清理完成: 删除 {deleted} 条过期 fact")
    except Exception as e:
        logger.error(f"[Scheduler] 记忆清理异常: {e}")


def _schedule_memory_cleanup():
    """注册每日 03:00 fact_memory 过期清理任务"""
    global _scheduler
    if _scheduler is None:
        return

    old_job = _scheduler.get_job(_get_memory_cleanup_job_id())
    if old_job:
        _scheduler.remove_job(_get_memory_cleanup_job_id())

    trigger = CronTrigger(hour=3, minute=0, second=0, timezone="Asia/Shanghai")
    _scheduler.add_job(
        _run_memory_cleanup,
        trigger=trigger,
        id=_get_memory_cleanup_job_id(),
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("[Scheduler] fact_memory 过期清理任务已注册: 03:00 (Asia/Shanghai)")
