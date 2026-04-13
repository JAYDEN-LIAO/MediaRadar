"""自适应并发限制器 — 根据成功率动态调整"""
import asyncio
import logging
from core.logger import get_logger

logger = get_logger("core.rate_limiter")

class AdaptiveSemaphore:
    """
    自适应信号量：
    - 连续成功 >= 3 次 → 并发 +1（上限 max）
    - 连续 rate error >= 2 次 → 并发 / 2（下限 min）
    """

    def __init__(self, name: str, initial: int = 5, min_val: int = 1, max_val: int = 20):
        self.name = name
        self._current = initial
        self._min = min_val
        self._max = max_val
        self._semaphore = asyncio.Semaphore(initial)
        self._consecutive_errors = 0
        self._consecutive_successes = 0

    async def acquire(self):
        await self._semaphore.acquire()

    def release(self):
        self._semaphore.release()

    def report_success(self):
        """报告一次成功调用"""
        self._consecutive_successes += 1
        self._consecutive_errors = 0
        if self._consecutive_successes >= 3 and self._current < self._max:
            self._adjust(min(self._max, self._current + 1))

    def report_rate_error(self):
        """报告一次限流错误"""
        self._consecutive_errors += 1
        self._consecutive_successes = 0
        if self._consecutive_errors >= 2 and self._current > self._min:
            self._adjust(max(self._min, self._current // 2))

    def _adjust(self, new_value: int):
        old = self._current
        self._current = new_value
        self._semaphore = asyncio.Semaphore(new_value)
        logger.info(f"[{self.name}] 并发限制调整: {old} → {new_value}")

    @property
    def current_limit(self) -> int:
        return self._current
