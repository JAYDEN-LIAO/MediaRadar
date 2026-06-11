"""
v2.2：模型配置表 CRUD（per-user，5 个 Agent 角色）

未配字段回退到 admin 设的 system default（settings.DEFAULT_* 等）
"""
from datetime import datetime
from typing import Optional

from core.database import get_db_connection
from core.logger import get_logger

logger = get_logger("core.modelcfg")


AGENT_ROLES = ("DEFAULT", "ANALYST", "REVIEWER", "EMBEDDING", "VISION", "AGENT")
PROVIDERS = ("deepseek", "kimi", "qwen", "openai", "custom", "")


# v2.2 P1#12：model_config 表 DDL 与 db_manager.init_radar_db 保持一致
_MODEL_CONFIG_DDL = '''
    CREATE TABLE IF NOT EXISTS model_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id TEXT NOT NULL,
        agent_role TEXT NOT NULL,
        provider TEXT,
        model TEXT,
        api_key TEXT,
        base_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(owner_id, agent_role)
    )
'''
_MODEL_CONFIG_INDEXES_DDL = [
    'CREATE INDEX IF NOT EXISTS idx_model_config_owner ON model_config(owner_id)',
]


def _ensure_model_config_table():
    """确保 model_config 表 + 索引存在（幂等，模块自包含）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_MODEL_CONFIG_DDL)
        for ddl in _MODEL_CONFIG_INDEXES_DDL:
            cursor.execute(ddl)
        conn.commit()


def _row_to_dict(row) -> dict:
    return dict(row)


def get_model_config(owner_id: str, agent_role: str) -> Optional[dict]:
    """查某用户某角色的模型配置"""
    if agent_role not in AGENT_ROLES:
        return None
    _ensure_model_config_table()
    with get_db_connection() as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM model_config WHERE owner_id = ? AND agent_role = ?",
            (owner_id, agent_role),
        )
        row = cursor.fetchone()
    return _row_to_dict(row) if row else None


def list_model_configs(owner_id: str) -> list[dict]:
    """列出某用户所有 5 个角色的配置（无配置的角色返回空记录）"""
    _ensure_model_config_table()
    with get_db_connection() as conn:
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM model_config WHERE owner_id = ? ORDER BY agent_role",
            (owner_id,),
        )
        rows = cursor.fetchall()
    existing = {r["agent_role"]: _row_to_dict(r) for r in rows}
    # 补齐 5 个角色（admin 系统默认回退由调用方处理）
    result = []
    for role in AGENT_ROLES:
        cfg = existing.get(role, {"owner_id": owner_id, "agent_role": role,
                                   "provider": "", "model": "", "api_key": "", "base_url": ""})
        # 隐藏 api_key 后缀（仅在 list 视图）
        result.append({
            "agent_role": role,
            "provider": cfg.get("provider", ""),
            "model": cfg.get("model", ""),
            "has_api_key": bool(cfg.get("api_key", "")),
            "base_url": cfg.get("base_url", ""),
            "updated_at": cfg.get("updated_at", ""),
        })
    return result


def upsert_model_config(
    owner_id: str,
    agent_role: str,
    provider: str = "",
    model: str = "",
    api_key: Optional[str] = None,
    base_url: str = "",
) -> dict:
    """插入或更新某用户某角色的模型配置"""
    if agent_role not in AGENT_ROLES:
        raise ValueError(f"invalid agent_role: {agent_role}")
    if provider and provider not in PROVIDERS:
        raise ValueError(f"invalid provider: {provider}")

    now = datetime.now().isoformat()
    _ensure_model_config_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 先读已存在记录
        cursor.execute(
            "SELECT api_key FROM model_config WHERE owner_id = ? AND agent_role = ?",
            (owner_id, agent_role),
        )
        existing = cursor.fetchone()
        # api_key 为 None 时保留旧值
        if api_key is None:
            api_key = existing[0] if existing else ""

        cursor.execute('''
            INSERT INTO model_config
                (owner_id, agent_role, provider, model, api_key, base_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, agent_role) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                api_key = excluded.api_key,
                base_url = excluded.base_url,
                updated_at = excluded.updated_at
        ''', (owner_id, agent_role, provider, model, api_key, base_url, now))
        conn.commit()
    logger.info(f"[ModelCfg] upsert owner={owner_id} role={agent_role} provider={provider} model={model}")
    return get_model_config(owner_id, agent_role) or {}


def delete_model_config(owner_id: str, agent_role: str) -> bool:
    """删除某角色配置（回退到系统默认）"""
    _ensure_model_config_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM model_config WHERE owner_id = ? AND agent_role = ?",
            (owner_id, agent_role),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_effective_config(owner_id: str, agent_role: str) -> dict:
    """
    获取用户的有效模型配置（user 配置 + system default 回退）。
    用于实际 LLM 调用。
    """
    user_cfg = get_model_config(owner_id, agent_role)
    # 系统默认从 settings 读（沿用现有 config.py 的 DEFAULT_* 字段）
    from core.config import settings

    def _field(name: str) -> str:
        # 优先 user 配置
        if user_cfg and user_cfg.get(name):
            return user_cfg[name]
        # 回退到 admin 系统默认
        if agent_role == "AGENT":
            return getattr(settings, f"DEFAULT_{name.upper()}", "") or ""
        if agent_role == "DEFAULT":
            return getattr(settings, f"DEFAULT_{name.upper()}", "") or ""
        return getattr(settings, f"DEFAULT_{name.upper()}", "") or ""

    return {
        "provider": (user_cfg or {}).get("provider", "deepseek") if user_cfg else "deepseek",
        "model": _field("model"),
        "api_key": _field("api_key"),
        "base_url": _field("base_url"),
        "is_user_override": user_cfg is not None and bool(user_cfg.get("model")),
    }
