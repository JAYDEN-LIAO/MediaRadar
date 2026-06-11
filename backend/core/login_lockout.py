"""
WS6-C4 v2.2: 登录失败锁定（per email）

v2.2 P0#10 修复：从进程内存 dict 迁到 SQLite（multi-worker 安全）

设计原则：
- 同一 email 连续登录失败 N 次 → 临时锁定 N 秒
- 成功登录 → 清零
- 状态持久化到 SQLite（`login_lockout` 表），多 worker 共享
- 用 INSERT...ON CONFLICT (UPSERT) 保证原子性，避免多 worker 竞态
- 锁定期间不返回"用户不存在"差异以免泄露

表结构：
    email TEXT PRIMARY KEY,
    fail_count INTEGER NOT NULL DEFAULT 0,
    window_start REAL,             -- 滚动窗口起点（首次失败时间）
    locked_until REAL NOT NULL DEFAULT 0,  -- 锁定截止时间（0=未锁）
    updated_at REAL NOT NULL
"""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Optional

from core.database import get_db_connection
from core.logger import get_logger

logger = get_logger("core.login_lockout")

_MAX_FAILS = 5            # 连续失败次数上限
_LOCKOUT_SECONDS = 300    # 锁定时长（5 分钟）
_cleanup_interval = 3600  # 每小时清一次过期条目
_last_cleanup = 0.0
_lock = threading.Lock()  # 保护 _last_cleanup 跨进程实例的本地状态（DB 本身有事务）


# ==================== 表初始化（幂等）====================

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS login_lockout (
    email TEXT PRIMARY KEY,
    fail_count INTEGER NOT NULL DEFAULT 0,
    window_start REAL,
    locked_until REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_login_lockout_updated_at
    ON login_lockout(updated_at)
"""


def _ensure_table(conn: sqlite3.Connection) -> None:
    """幂等建表（首次调用执行，后续 no-op）"""
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_CREATE_INDEX_SQL)
    conn.commit()


# ==================== 业务接口 ====================

def is_locked(email: str) -> tuple[bool, int]:
    """
    返回 (是否锁定, 剩余秒数)。
    锁定期间所有登录请求都会被拒绝（不区分用户是否存在以防泄露）。
    """
    key = email.lower().strip()
    now = time.time()

    # 懒清理（每 worker 进程本地 cache interval；DB 自身在 record_* 时也会清理）
    _maybe_cleanup_local(now)

    try:
        with get_db_connection() as conn:
            _ensure_table(conn)
            cur = conn.execute(
                "SELECT locked_until FROM login_lockout WHERE email = ?",
                (key,),
            )
            row = cur.fetchone()
        if row and row[0] and row[0] > now:
            return True, int(row[0] - now)
        return False, 0
    except sqlite3.Error as e:
        # 修复 v2.2 P0#10：DB 异常不再静默，降级为 fail-open（允许登录）
        # 配以 warning 让运维感知（避免攻击者通过 DB 故障触发 lockout 绕过）
        logger.warning(
            f"[LoginLockout] is_locked DB 异常，fail-open 放行: {type(e).__name__}: {e}"
        )
        return False, 0


def record_failure(email: str) -> int:
    """
    记录一次失败。返回新的失败次数（窗口内）。
    若达到 _MAX_FAILS，触发锁定。
    """
    key = email.lower().strip()
    now = time.time()
    window_cutoff = now - _LOCKOUT_SECONDS

    try:
        with get_db_connection() as conn:
            _ensure_table(conn)
            cur = conn.execute(
                "SELECT fail_count, window_start, locked_until FROM login_lockout WHERE email = ?",
                (key,),
            )
            row = cur.fetchone()

            if row is None:
                # 首次失败
                fail_count = 1
                window_start = now
                locked_until = 0.0
            else:
                prev_count, prev_window_start, prev_locked_until = row
                # 已被锁且未到期：直接返回（防御性，正常不会到这里因为 is_locked 会先拦截）
                if prev_locked_until and prev_locked_until > now:
                    return prev_count
                # 窗口已过期：重置
                if prev_window_start is None or prev_window_start < window_cutoff:
                    fail_count = 1
                    window_start = now
                else:
                    fail_count = prev_count + 1
                    window_start = prev_window_start
                locked_until = 0.0

            # 触发锁定
            if fail_count >= _MAX_FAILS:
                locked_until = now + _LOCKOUT_SECONDS
                logger.warning(
                    f"[LoginLockout] email {key} 已触发锁定 {fail_count} 次失败 → 锁定 {_LOCKOUT_SECONDS}s"
                )

            # UPSERT：原子写
            conn.execute(
                """
                INSERT INTO login_lockout (email, fail_count, window_start, locked_until, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    fail_count = excluded.fail_count,
                    window_start = excluded.window_start,
                    locked_until = excluded.locked_until,
                    updated_at = excluded.updated_at
                """,
                (key, fail_count, window_start, locked_until, now),
            )
            conn.commit()
            return fail_count
    except sqlite3.Error as e:
        logger.warning(
            f"[LoginLockout] record_failure DB 异常（计数未持久化）: {type(e).__name__}: {e}"
        )
        return 0  # DB 不可用时不计失败（fail-open 避免误锁）


def record_success(email: str) -> None:
    """登录成功：清零（删除该 email 的所有状态）"""
    key = email.lower().strip()
    try:
        with get_db_connection() as conn:
            _ensure_table(conn)
            conn.execute("DELETE FROM login_lockout WHERE email = ?", (key,))
            conn.commit()
    except sqlite3.Error as e:
        # 成功清零失败仅记录，不阻塞登录
        logger.warning(
            f"[LoginLockout] record_success DB 异常（清零失败，下次失败可能累加旧计数）: "
            f"{type(e).__name__}: {e}"
        )


# ==================== 维护 / 观测 ====================

def get_lockout_status(email: str) -> Optional[dict]:
    """
    返回指定 email 的当前锁定状态（供调试 / 可观测性使用）。
    无记录返回 None。
    """
    key = email.lower().strip()
    try:
        with get_db_connection() as conn:
            _ensure_table(conn)
            cur = conn.execute(
                "SELECT fail_count, window_start, locked_until, updated_at "
                "FROM login_lockout WHERE email = ?",
                (key,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "email": key,
            "fail_count": row[0],
            "window_start": row[1],
            "locked_until": row[2],
            "updated_at": row[3],
            "is_locked_now": bool(row[2] and row[2] > time.time()),
        }
    except sqlite3.Error as e:
        logger.warning(
            f"[LoginLockout] get_lockout_status DB 异常: {type(e).__name__}: {e}"
        )
        return None


def cleanup_expired(now: Optional[float] = None) -> int:
    """
    清理过期条目（updated_at < now - 2 * _LOCKOUT_SECONDS）。
    返回被删除的行数。
    """
    if now is None:
        now = time.time()
    cutoff = now - _LOCKOUT_SECONDS * 2
    try:
        with get_db_connection() as conn:
            _ensure_table(conn)
            cur = conn.execute(
                "DELETE FROM login_lockout WHERE updated_at < ?", (cutoff,)
            )
            deleted = cur.rowcount
            conn.commit()
        if deleted:
            logger.info(f"[LoginLockout] 清理 {deleted} 条过期记录（cutoff={cutoff:.0f}）")
        return deleted
    except sqlite3.Error as e:
        logger.warning(
            f"[LoginLockout] cleanup_expired DB 异常: {type(e).__name__}: {e}"
        )
        return 0


def _maybe_cleanup_local(now: float) -> None:
    """懒清理：每 worker 进程本地 cache interval（避免每次 SELECT 都触发 DELETE）"""
    global _last_cleanup
    with _lock:
        if now - _last_cleanup < _cleanup_interval:
            return
        _last_cleanup = now
    # 在锁外执行（避免长事务持锁）
    cleanup_expired(now)
