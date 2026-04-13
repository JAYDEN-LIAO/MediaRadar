"""API Key 鉴权 — FastAPI Security 依赖"""
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from functools import lru_cache

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

@lru_cache()
def get_valid_api_keys() -> set[str]:
    """从配置读取有效 API Key 列表（逗号分隔）"""
    try:
        from core.config import settings
        keys_str = getattr(settings, 'API_KEYS', '') or ""
    except Exception:
        keys_str = ""
    return set(k.strip() for k in keys_str.split(",") if k.strip())

async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """FastAPI 依赖项：验证 X-API-Key Header"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-API-Key Header"
        )
    if api_key not in get_valid_api_keys():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key"
        )
    return api_key

def verify_api_key_sync(api_key: str = Security(API_KEY_HEADER)) -> str:
    """同步版本（非 async 路由使用）"""
    return verify_api_key(api_key)
