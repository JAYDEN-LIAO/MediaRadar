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
    """签发 access JWT（v2.2 P1#14：标记 token_type=access 以区分 refresh）

    向后兼容：保留旧签名，type 字段缺失时 decode_token 视为 access。
    """
    return encode_access_token(user_id, role, extra_claims=extra_claims)


def encode_access_token(user_id: str, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """签发 access JWT（24h 短期，用于 API 鉴权）"""
    now = datetime.utcnow()
    expire = now + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def encode_refresh_token(user_id: str, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """签发 refresh JWT（7 天，仅用于 /api/auth/refresh 换 access token）

    安全约束：
    - type=refresh（用于与 access token 区分）
    - role 嵌在 payload 里（防止用户升 admin 后旧 refresh 还能签 admin token 时
      仍按 role 字段返回，但生产环境应配合 token 黑名单或用户状态检查）
    """
    now = datetime.utcnow()
    expire = now + timedelta(hours=settings.JWT_REFRESH_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_token(token: str, expected_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    验签 + 解码。失败/过期/黑名单 → None

    expected_type（v2.2 P1#14 新增）：
      - None：不检查 type 字段（向后兼容旧 access token）
      - "access"：必须是 type=access，refresh token 调这里会被拒
      - "refresh"：必须是 type=refresh，access token 调这里会被拒
      - 旧 token（无 type 字段）：None 时按 access 处理；"refresh" 显式要求时按不符拒

    L2 v2.2: 额外检查用户表 tokens_invalid_after 字段。
    若 token 的 iat 早于该时间戳，则视为已被撤销（如账号被停用）。
    """
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
    except jwt.ExpiredSignatureError:
        logger.info("[JWT] token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"[JWT] token 无效: {e}")
        return None

    # v2.2 P1#14：type 字段校验
    actual_type = payload.get("type")
    if expected_type is not None:
        # 显式要求 type 时：缺失视为不匹配
        if actual_type != expected_type:
            logger.warning(
                f"[JWT] type 不匹配: 期望={expected_type}, 实际={actual_type!r}"
            )
            return None
    else:
        # 默认兼容模式：缺失 type 字段视为 access（保持向后兼容）
        if actual_type is None:
            payload["type"] = "access"

    # L2 v2.2: 撤销时间戳检查（deactivate / 主动踢下线会设置此字段）
    user_id = payload.get("sub")
    iat = payload.get("iat")
    if user_id and iat is not None:
        try:
            inv_after = auth_db.get_tokens_invalid_after(user_id)
            if inv_after is not None:
                # 解析为 UTC 秒数
                from datetime import datetime as _dt
                inv_ts = _dt.fromisoformat(inv_after).timestamp()
                if iat <= inv_ts:
                    logger.warning(f"[JWT] token 已被批量撤销（user={user_id[:8]}...）")
                    return None
        except Exception as e:
            # 检查失败不阻塞登录，但记日志
            logger.warning(f"[JWT] tokens_invalid_after 检查异常: {e}")

    return payload


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
