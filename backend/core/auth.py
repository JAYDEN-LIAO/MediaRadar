"""API Key 鉴权 — FastAPI Security 依赖"""
import time
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# v2.2: 去掉 @lru_cache，改用 60s TTL 缓存
_cached_keys: set[str] | None = None
_cached_at: float = 0
_CACHE_TTL = 60


def get_valid_api_keys() -> set[str]:
    """从配置读取有效 API Key 列表（逗号分隔），60s 缓存"""
    global _cached_keys, _cached_at
    now = time.time()
    if _cached_keys is not None and (now - _cached_at) < _CACHE_TTL:
        return _cached_keys
    try:
        from core.config import settings
        keys_str = getattr(settings, 'API_KEYS', '') or ""
    except Exception:
        keys_str = ""
    _cached_keys = set(k.strip() for k in keys_str.split(",") if k.strip())
    _cached_at = now
    return _cached_keys
