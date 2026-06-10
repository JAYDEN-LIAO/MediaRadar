"""
v2.2：配额表 CRUD + 检查函数

每个用户 1 条 quota 记录（按 owner_id 主键），admin 可在 /admin/quota 调整。
"""
from datetime import datetime
from typing import Optional

from core.database import get_db_connection
from core.logger import get_logger

logger = get_logger("core.quota")


DEFAULT_MAX_SUBSCRIPTIONS = 20
DEFAULT_HISTORY_RETENTION_DAYS = 30
DEFAULT_MAX_CHAT_PER_MONTH = 200


def _ensure_quota_row(owner_id: str) -> None:
    """确保某用户有 quota 行（首次查询时自动建默认）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM quota WHERE owner_id = ?", (owner_id,))
        if cursor.fetchone() is None:
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO quota
                (owner_id, max_subscriptions, history_retention_days,
                 max_chat_per_month, used_chat_this_month, month_reset_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
            ''', (owner_id, DEFAULT_MAX_SUBSCRIPTIONS, DEFAULT_HISTORY_RETENTION_DAYS,
                  DEFAULT_MAX_CHAT_PER_MONTH, now, now))
            conn.commit()


def get_quota(owner_id: str) -> dict:
    """获取某用户的配额（不存在则建默认）"""
    _ensure_quota_row(owner_id)
    with get_db_connection() as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quota WHERE owner_id = ?", (owner_id,))
        row = cursor.fetchone()
    return dict(row) if row else {}


def update_quota(owner_id: str, **fields) -> Optional[dict]:
    """更新配额（admin 用）"""
    allowed = {
        "max_subscriptions", "history_retention_days", "max_chat_per_month",
    }
    sets = []
    params = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if not isinstance(v, int) or v < 0:
            raise ValueError(f"invalid quota value for {k}: {v}")
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return get_quota(owner_id)
    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(owner_id)
    _ensure_quota_row(owner_id)
    sql = f"UPDATE quota SET {', '.join(sets)} WHERE owner_id = ?"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
    return get_quota(owner_id)


def check_quota(owner_id: str, resource: str) -> tuple[bool, str]:
    """
    检查配额。返回 (ok, msg)。
    resource: "subscription" | "chat"
    """
    q = get_quota(owner_id)
    if resource == "subscription":
        from core.subscription_db import count_subscriptions
        used = count_subscriptions(owner_id)
        max_n = q.get("max_subscriptions", DEFAULT_MAX_SUBSCRIPTIONS)
        if used >= max_n:
            return False, f"已达订阅上限（{used}/{max_n}），请到设置中调整或删除旧订阅"
        return True, ""
    if resource == "chat":
        # 检查是否需要月度重置
        _maybe_reset_monthly(owner_id, q)
        used = q.get("used_chat_this_month", 0)
        max_n = q.get("max_chat_per_month", DEFAULT_MAX_CHAT_PER_MONTH)
        if used >= max_n:
            return False, f"本月 Chat 消息数已用完（{used}/{max_n}），下月 1 日重置"
        return True, ""
    return True, ""


def increment_chat_count(owner_id: str) -> None:
    """chat 消息 +1（配额计数）"""
    _ensure_quota_row(owner_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE quota SET used_chat_this_month = used_chat_this_month + 1, updated_at = ? WHERE owner_id = ?",
            (datetime.now().isoformat(), owner_id),
        )
        conn.commit()


def _maybe_reset_monthly(owner_id: str, q: dict) -> None:
    """若距 month_reset_at 超过 30 天，重置月度计数"""
    last_reset = q.get("month_reset_at")
    if not last_reset:
        return
    try:
        last_dt = datetime.fromisoformat(last_reset)
    except (TypeError, ValueError):
        return
    delta = datetime.now() - last_dt
    if delta.days >= 30:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE quota SET used_chat_this_month = 0, month_reset_at = ? WHERE owner_id = ?",
                (datetime.now().isoformat(), owner_id),
            )
            conn.commit()
        logger.info(f"[Quota] owner={owner_id} 月度计数重置（30 天到期）")


def get_default_quota_values() -> dict:
    """返回系统默认值（供 admin 查看）"""
    return {
        "max_subscriptions": DEFAULT_MAX_SUBSCRIPTIONS,
        "history_retention_days": DEFAULT_HISTORY_RETENTION_DAYS,
        "max_chat_per_month": DEFAULT_MAX_CHAT_PER_MONTH,
    }
