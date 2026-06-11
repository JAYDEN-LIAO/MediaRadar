"""
搜索历史会话缓存（per-owner，单进程内存）

P1 简化：以 owner_id 为 key；session 维度等 P3 chat session 接入后再加。
Cache 上限 50 条/owner，FIFO；v2.2 起每条记录附带 TTL，过期自动剔除。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

_MAX_PER_OWNER = 50
_TTL_SECONDS = 7 * 24 * 3600  # v2.2：单条记录 7 天后过期
_lock = Lock()
_cache: dict[str, deque] = {}


def _drop_expired(dq: deque) -> None:
    """从队首剔除过期条目（O(过期数)）。"""
    cutoff = datetime.now() - timedelta(seconds=_TTL_SECONDS)
    while dq:
        first = dq[0]
        try:
            ts = datetime.fromisoformat(first["timestamp"])
        except (KeyError, ValueError, TypeError):
            dq.popleft()
            continue
        if ts < cutoff:
            dq.popleft()
        else:
            break


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
        _drop_expired(dq)
        dq.append(entry)


def list_history(owner_id: str) -> list[dict]:
    with _lock:
        dq = _cache.get(owner_id)
        if not dq:
            return []
        _drop_expired(dq)
        # 最新在前
        return list(reversed(dq))


def clear_history(owner_id: str) -> int:
    with _lock:
        dq = _cache.get(owner_id)
        count = len(dq) if dq else 0
        if dq is not None:
            dq.clear()
        return count
