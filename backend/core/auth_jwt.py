"""
WS4: JWT 签发 / 验签 / 黑名单

- 默认 24h 过期
- HS256 对称签名（生产建议用 RS256 切到公私钥）
- 验签时同步检查 token_blacklist 表
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt

from core.config import settings
from core.logger import get_logger
from core import auth_db

logger = get_logger("auth.jwt")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encode_token(user_id: str, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """签发 JWT"""
    now = datetime.utcnow()
    expire = now + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """验签 + 解码。失败/过期/黑名单 → None"""
    # 先查黑名单
    if auth_db.is_blacklisted(_hash_token(token)):
        logger.warning("[JWT] token 已被加入黑名单")
        return None

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("[JWT] token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"[JWT] token 无效: {e}")
        return None


def revoke_token(token: str) -> bool:
    """撤销 token：写入黑名单（带过期时间）"""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": False},  # 即使已过期也允许撤销
    )
    exp_ts = payload.get("exp")
    if not exp_ts:
        return False
    expires_at = datetime.fromtimestamp(exp_ts).isoformat()
    auth_db.add_to_blacklist(_hash_token(token), expires_at)
    return True
