from qdrant_client import QdrantClient
from functools import lru_cache

@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """单例 Qdrant 客户端，所有模块复用同一实例"""
    try:
        from core.config import settings
        return QdrantClient(
            host=getattr(settings, 'QDRANT_HOST', '127.0.0.1'),
            port=getattr(settings, 'QDRANT_PORT', 6333),
            timeout=10,
        )
    except Exception:
        # fallback 避免启动失败
        return QdrantClient(host="127.0.0.1", port=6333, timeout=10)
