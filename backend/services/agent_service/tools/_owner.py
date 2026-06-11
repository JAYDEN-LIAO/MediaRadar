"""
owner_id 上下文注入。

API 入口（/api/agent/chat）拿到 current_user 后调 `set_current_owner(user_id)`，
工具实现里用 `@with_owner` 装饰即可在 kwargs 拿到 `_owner_id`。

LLM 永远不会传 _owner_id（schema 里也不暴露），这是后端强制注入，
保证数据隔离不可绕过。
"""
from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Callable, Optional

# 当前请求的 owner_id；None 表示未登录（工具应拒绝执行）
_current_owner_id: ContextVar[Optional[str]] = ContextVar(
    "mediaradar_current_owner_id", default=None
)


def set_current_owner(owner_id: Optional[str]):
    """API 入口调用：把当前用户写入 contextvar，返回 Token 以便 reset。"""
    return _current_owner_id.set(owner_id)


def reset_current_owner(token) -> None:
    """配合 set_current_owner 的 Token 使用，避免污染下一请求。"""
    _current_owner_id.reset(token)


def get_current_owner() -> Optional[str]:
    return _current_owner_id.get()


class OwnerRequiredError(RuntimeError):
    """工具尝试访问 owner_id 但上下文为空（未登录或忘记 set）。"""


def with_owner(func: Callable) -> Callable:
    """装饰器：从 contextvar 取 owner_id 注入到 kwargs['_owner_id']。

    - 若 LLM args 中已含 _owner_id，忽略并覆盖（防伪造）
    - 若上下文无 owner_id，抛 OwnerRequiredError
    - 自动适配 sync / async / async generator 函数
    """
    if inspect.isasyncgenfunction(func):

        @wraps(func)
        async def async_gen_wrapper(*args, **kwargs):
            owner_id = _current_owner_id.get()
            if not owner_id:
                raise OwnerRequiredError(
                    f"tool '{getattr(func, '_tool_name', func.__name__)}' "
                    "requires authenticated owner_id in context"
                )
            kwargs["_owner_id"] = owner_id
            async for item in func(*args, **kwargs):
                yield item

        return async_gen_wrapper

    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            owner_id = _current_owner_id.get()
            if not owner_id:
                raise OwnerRequiredError(
                    f"tool '{getattr(func, '_tool_name', func.__name__)}' "
                    "requires authenticated owner_id in context"
                )
            kwargs["_owner_id"] = owner_id
            return await func(*args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        owner_id = _current_owner_id.get()
        if not owner_id:
            raise OwnerRequiredError(
                f"tool '{getattr(func, '_tool_name', func.__name__)}' "
                "requires authenticated owner_id in context"
            )
        kwargs["_owner_id"] = owner_id
        return func(*args, **kwargs)

    return sync_wrapper
