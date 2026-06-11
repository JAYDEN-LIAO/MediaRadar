"""
WS4: FastAPI 依赖注入

- get_current_user: 解析 Bearer token，返回 user dict
- require_admin: 仅 admin 通过，否则 403
- get_optional_user: 有 token 就解析，没有返回 None（公开端点用）
"""
from fastapi import Header, HTTPException, status, Depends, Security
from typing import Optional, Dict, Any

from core.auth_jwt import decode_token
from core.auth_db import get_user_by_id
from core.logger import get_logger
from core.auth import API_KEY_HEADER, get_valid_api_keys

logger = get_logger("auth.deps")


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI 依赖项：从 Authorization: Bearer <token> 解析当前用户"""
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "msg": "未登录或 token 缺失", "data": None},
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "msg": "token 无效或已过期", "data": None},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "msg": "token payload 缺少 sub", "data": None},
        )

    user = get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "msg": "用户不存在或已禁用", "data": None},
        )
    return user


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[Dict[str, Any]]:
    """公开端点用：有 token 解析用户，无 token 返回 None"""
    token = _extract_bearer(authorization)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    return user if user and user.get("is_active") else None


async def get_current_user_or_api_key(
    authorization: Optional[str] = Header(default=None),
    api_key: Optional[str] = Security(API_KEY_HEADER),
) -> Dict[str, Any]:
    """
    v2.2 P1#16：接受 JWT（Bearer token）或 API Key（X-API-Key），任一即可。

    策略：
      1. 优先尝试 JWT：成功 → 返回完整 user dict
      2. 回退到 API Key：有效 → 返回最小服务账户 dict（不映射到具体用户）
      3. 都失败 → 401

    用于同时需要前端（JWT）和外部工具（API Key）访问的端点，
    比如 /api/start_task 和 /api/radar_status。
    """
    # 先试 JWT
    token = _extract_bearer(authorization)
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                user = get_user_by_id(user_id)
                if user and user.get("is_active"):
                    return user

    # 再试 API Key
    if api_key and api_key in get_valid_api_keys():
        return {"id": "api_service", "role": "admin", "is_active": True}

    # 都失败
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": 401, "msg": "需要有效的 JWT（Bearer token）或 API Key（X-API-Key）", "data": None},
    )


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """仅 admin 通过；普通用户 → 403"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 403, "msg": "需要 admin 权限", "data": None},
        )
    return current_user
