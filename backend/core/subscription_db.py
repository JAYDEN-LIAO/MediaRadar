"""
v2.2：订阅表 CRUD（per-owner，替代 system_settings.keywords）

订阅包含 name / type / polarity / sensitivity / push_mode / platforms 等字段，
数据存储在 subscriptions 表中，所有操作强制 owner_id 隔离。
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from core.database import get_db_connection
from core.logger import get_logger

logger = get_logger("core.sub")


VALID_TYPES = ("person", "brand", "event", "industry", "keyword")
VALID_POLARITY = ("negative", "positive", "neutral", "all")
VALID_SENSITIVITY = ("conservative", "balanced", "aggressive")
VALID_PUSH_MODE = ("every", "important", "silent", "off")


# v2.2 P1#12：subscription 表 DDL 与 db_manager.init_radar_db 保持一致
_SUBSCRIPTION_DDL = '''
    CREATE TABLE IF NOT EXISTS subscription (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'keyword',
        polarity TEXT DEFAULT 'all',
        sensitivity TEXT DEFAULT 'balanced',
        frequency_min INTEGER DEFAULT 60,
        platforms TEXT DEFAULT '[]',
        push_mode TEXT DEFAULT 'important',
        show_risk_alert INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
'''
_SUBSCRIPTION_INDEXES_DDL = [
    'CREATE INDEX IF NOT EXISTS idx_subscription_owner ON subscription(owner_id)',
    'CREATE INDEX IF NOT EXISTS idx_subscription_active ON subscription(is_active)',
]


def _ensure_subscription_table():
    """确保 subscription 表 + 索引存在（幂等，模块自包含）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_SUBSCRIPTION_DDL)
        for ddl in _SUBSCRIPTION_INDEXES_DDL:
            cursor.execute(ddl)
        conn.commit()


def _gen_id() -> str:
    return f"s_{uuid.uuid4().hex[:16]}"


def _row_to_dict(row) -> dict:
    d = dict(row)
    # platforms JSON → list
    try:
        d["platforms"] = json.loads(d.get("platforms", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["platforms"] = []
    # show_risk_alert INTEGER → bool
    d["show_risk_alert"] = bool(d.get("show_risk_alert", 0))
    d["is_active"] = bool(d.get("is_active", 1))
    return d


def create_subscription(
    owner_id: str,
    name: str,
    type: str = "keyword",
    polarity: str = "all",
    sensitivity: str = "balanced",
    frequency_min: int = 60,
    platforms: Optional[list] = None,
    push_mode: str = "important",
    show_risk_alert: bool = False,
) -> dict:
    """新增订阅。返回完整订阅 dict。"""
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type: {type}")
    if polarity not in VALID_POLARITY:
        raise ValueError(f"invalid polarity: {polarity}")
    if sensitivity not in VALID_SENSITIVITY:
        raise ValueError(f"invalid sensitivity: {sensitivity}")
    if push_mode not in VALID_PUSH_MODE:
        raise ValueError(f"invalid push_mode: {push_mode}")

    sub_id = _gen_id()
    now = datetime.now().isoformat()
    plat_json = json.dumps(platforms or [], ensure_ascii=False)
    _ensure_subscription_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscription
            (id, owner_id, name, type, polarity, sensitivity, frequency_min,
             platforms, push_mode, show_risk_alert, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ''', (sub_id, owner_id, name, type, polarity, sensitivity, frequency_min,
              plat_json, push_mode, int(show_risk_alert), now, now))
        conn.commit()
    logger.info(f"[Sub] 新增订阅: id={sub_id} owner={owner_id} name={name} type={type}")
    return get_subscription_by_id(owner_id, sub_id)  # type: ignore


def get_subscription_by_id(owner_id: str, sub_id: str, is_admin: bool = False) -> Optional[dict]:
    """按 id 查订阅（per-owner 隔离）"""
    _ensure_subscription_table()
    with get_db_connection() as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        if is_admin:
            cursor.execute("SELECT * FROM subscription WHERE id = ?", (sub_id,))
        else:
            cursor.execute(
                "SELECT * FROM subscription WHERE id = ? AND owner_id = ?",
                (sub_id, owner_id),
            )
        row = cursor.fetchone()
    return _row_to_dict(row) if row else None


def list_subscriptions(owner_id: str, is_admin: bool = False, include_inactive: bool = False) -> list:
    """列出某用户的所有订阅"""
    _ensure_subscription_table()
    with get_db_connection() as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        if is_admin and include_inactive:
            cursor.execute("SELECT * FROM subscription ORDER BY created_at DESC")
        elif is_admin:
            cursor.execute("SELECT * FROM subscription WHERE is_active = 1 ORDER BY created_at DESC")
        elif include_inactive:
            cursor.execute(
                "SELECT * FROM subscription WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM subscription WHERE owner_id = ? AND is_active = 1 ORDER BY created_at DESC",
                (owner_id,),
            )
        rows = cursor.fetchall()
    return [_row_to_dict(r) for r in rows]


def update_subscription(owner_id: str, sub_id: str, **fields) -> Optional[dict]:
    """更新订阅字段。仅更新传入的字段。

    M8 v2.2：防御深度——显式拒绝 owner_id 注入（白名单已隐式过滤，但
    即便将来扩展白名单也不允许通过此入口修改 owner_id）。
    """
    if not fields:
        return get_subscription_by_id(owner_id, sub_id)

    # M8 v2.2: 显式拒绝 owner_id 注入（白名单虽已过滤，这里再加一道保险）
    if "owner_id" in fields:
        raise ValueError("owner_id 不可通过 update_subscription 修改")

    # 字段白名单 + 值校验
    allowed = {
        "name", "type", "polarity", "sensitivity", "frequency_min",
        "platforms", "push_mode", "show_risk_alert", "is_active",
    }
    sets = []
    params = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "type" and v not in VALID_TYPES:
            raise ValueError(f"invalid type: {v}")
        if k == "polarity" and v not in VALID_POLARITY:
            raise ValueError(f"invalid polarity: {v}")
        if k == "sensitivity" and v not in VALID_SENSITIVITY:
            raise ValueError(f"invalid sensitivity: {v}")
        if k == "push_mode" and v not in VALID_PUSH_MODE:
            raise ValueError(f"invalid push_mode: {v}")
        if k == "platforms" and isinstance(v, list):
            v = json.dumps(v, ensure_ascii=False)
        if k == "show_risk_alert":
            v = int(bool(v))
        if k == "is_active":
            v = int(bool(v))
        sets.append(f"{k} = ?")
        params.append(v)
    if not sets:
        return get_subscription_by_id(owner_id, sub_id)

    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.extend([sub_id, owner_id])

    sql = f"UPDATE subscription SET {', '.join(sets)} WHERE id = ? AND owner_id = ?"
    _ensure_subscription_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
        if cursor.rowcount == 0:
            return None
    return get_subscription_by_id(owner_id, sub_id)


def delete_subscription(owner_id: str, sub_id: str) -> bool:
    """软删除（is_active=0）。返回是否成功。"""
    _ensure_subscription_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE subscription SET is_active = 0, updated_at = ? WHERE id = ? AND owner_id = ?",
            (datetime.now().isoformat(), sub_id, owner_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def count_subscriptions(owner_id: str, is_admin: bool = False) -> int:
    """计数（用于配额检查）"""
    _ensure_subscription_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if is_admin:
            cursor.execute("SELECT COUNT(*) FROM subscription WHERE is_active = 1")
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM subscription WHERE owner_id = ? AND is_active = 1",
                (owner_id,),
            )
        return cursor.fetchone()[0]


