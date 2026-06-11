"""自适应并发限制器 — 根据成功率动态调整（WS3 新增 HTTP 全局限流）"""
import asyncio
import time
import logging
from collections import defaultdict
from typing import Callable, Awaitable
from fastapi import FastAPI, Request, Response
from core.logger import get_logger
from core.config import settings

logger = get_logger("core.rate_limiter")


# ============================================================
# WS3.1: 滑动窗口 HTTP 全局限流
# ============================================================

class SlidingWindowRateLimiter:
    """
    内存滑动窗口限流器（按 IP / 用户 ID）。

    设计:
    - 每个 key (IP 或 user_id) 独立计数
    - 窗口大小 60s，每个窗口内允许 limit 次请求
    - 过期 key 自动清理（惰性删除）

    限流策略分层:
        default: 60 次/分钟（普通端点）
        auth:    10 次/分钟（登录/注册/密码重置）
        sensitive: 30 次/分钟（涉及敏感操作的端点）
    """

    def __init__(self):
        self._windows: dict[str, list] = defaultdict(list)  # key -> [timestamp, ...]
        self._default_window: int = 60       # 秒
        self._default_limit: int = 60        # 次/窗口
        self._auth_window: int = 60
        self._auth_limit: int = 5            # WS6-C4 v2.2: 注册/登录 10→5（防爆破）
        self._sensitive_window: int = 60
        self._sensitive_limit: int = 30
        self._cleanup_interval: int = 300    # 每 5 分钟清理一次过期 key
        self._last_cleanup: float = time.time()

    def _make_key(self, request: Request) -> str:
        """生成限流 key：优先 user_id，其次 IP"""
        user_id = getattr(request.state, "user_id", "") or ""
        if user_id:
            return f"user:{user_id}"
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """根据路径返回 (窗口秒数, 限制次数)"""
        auth_paths = ("/api/auth/", "/api/user/register", "/api/user/login")
        sensitive_paths = ("/api/settings", "/api/llm/config", "/api/push/config")
        if any(path.startswith(p) for p in auth_paths):
            return self._auth_window, self._auth_limit
        if any(path.startswith(p) for p in sensitive_paths):
            return self._sensitive_window, self._sensitive_limit
        return self._default_window, self._default_limit

    def _periodic_cleanup(self):
        """惰性清理过期记录"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        threshold = now - max(self._default_window, self._auth_window, self._sensitive_window) - 10
        keys_to_delete = []
        for key, timestamps in list(self._windows.items()):
            # 只保留最近 N 秒内的记录
            valid = [t for t in timestamps if t >= threshold]
            if valid:
                self._windows[key] = valid
            else:
                keys_to_delete.append(key)
        for k in keys_to_delete:
            del self._windows[k]
        if keys_to_delete:
            logger.debug(f"[RateLimiter] 清理过期限流记录: {len(keys_to_delete)} keys")

    def check(self, request: Request) -> tuple[bool, int, int]:
        """
        检查是否允许请求通过。

        Returns:
            (allowed: bool, remaining: int, retry_after: int)
            retry_after: 如果被限，多少秒后可以重试
        """
        self._periodic_cleanup()
        key = self._make_key(request)
        window, limit = self._get_limit_for_path(request.url.path)
        now = time.time()
        cutoff = now - window

        # 获取当前窗口记录
        timestamps = self._windows[key]
        # 只保留窗口内的
        valid = [t for t in timestamps if t >= cutoff]
        self._windows[key] = valid

        if len(valid) >= limit:
            # 被限流：计算最早何时过期
            oldest = valid[0] if valid else now
            retry_after = int(window - (now - oldest) + 1)
            return False, 0, retry_after

        # 允许通过
        remaining = limit - len(valid) - 1
        return True, remaining, 0


# 全局限流器实例
_rate_limiter = SlidingWindowRateLimiter()


def add_rate_limiting_middleware(app: FastAPI):
    """
    挂载全局限流中间件（所有 /api/* 路由受保护）。
    """
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        # 仅对 API 路由限流
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # /metrics 不受限流
        if request.url.path == "/metrics":
            return await call_next(request)

        # v2.2 P1#15：未认证请求只限流 auth 端点（login/register/OAuth），
        # 其他端点放行（后续 endpoint 的 auth dependency 会拒）。
        # 这防止攻击者通过大量无认证请求耗尽 IP 级配额，误伤正常用户。
        _auth_paths = ("/api/auth/", "/api/user/register", "/api/user/login", "/api/auth/refresh")
        _is_auth_path = any(request.url.path.startswith(p) for p in _auth_paths)
        _has_auth = bool(getattr(request.state, "user_id", ""))
        if not _has_auth and not _is_auth_path:
            return await call_next(request)

        allowed, remaining, retry_after = _rate_limiter.check(request)
        response: Response = await call_next(request) if allowed else Response(
            status_code=429,
            content='{"code": 429, "msg": "请求过于频繁，请稍后再试", "data": null}',
            media_type="application/json",
        )

        # 注入限流响应头
        response.headers["X-RateLimit-Limit"] = "60"
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        if retry_after > 0:
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + retry_after))

        return response

    logger.info("[RateLimiter] 全局限流中间件已挂载")


# 原有的 AdaptivSemaphore 保持不变
class AdaptiveSemaphore:
    """自适应信号量（用于并发任务控制，非 HTTP 限流）"""
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
        self._consecutive_successes += 1
        self._consecutive_errors = 0
        if self._consecutive_successes >= 3 and self._current < self._max:
            self._adjust(min(self._max, self._current + 1))

    def report_rate_error(self):
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
