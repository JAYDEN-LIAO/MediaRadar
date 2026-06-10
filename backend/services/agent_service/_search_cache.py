"""
搜索历史会话缓存（per-owner，单进程内存）

P1 简化：以 owner_id 为 key；session 维度等 P3 chat session 接入后再加。
Cache 上限 50 条/owner，FIFO。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Optional

_MAX_PER_OWNER = 50
_lock = Lock()
_cache: dict[str, deque] = {}


def record_search(owner_id: str, query: str, result_count: int) -> None:
    if not owner_id:
        return
    entry = {
        "query": query,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "result_count": int(result_count),
    }
    with _lock:
        dq = _cache.setdefault(owner_id, deque(maxlen=_MAX_PER_OWNER))
        dq.append(entry)


def list_history(owner_id: str) -> list[dict]:
    with _lock:
        dq = _cache.get(owner_id)
        if not dq:
            return []
        # 最新在前
        return list(reversed(dq))


def clear_history(owner_id: str) -> int:
    with _lock:
        dq = _cache.get(owner_id)
        count = len(dq) if dq else 0
        if dq is not None:
            dq.clear()
        return count
