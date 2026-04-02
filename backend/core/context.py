# backend/core/context.py
"""
请求上下文管理 - 用于在异步/多线程环境中传递任务上下文
"""
import uuid
import threading
from contextvars import ContextVar
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class TaskContext:
    """任务上下文数据类"""
    task_id: str = ""
    keyword: str = ""
    platform: str = ""
    target_keyword: str = ""
    user_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "keyword": self.keyword,
            "platform": self.platform,
            "target_keyword": self.target_keyword,
            "user_id": self.user_id,
            "extra": self.extra,
        }


# 使用 ContextVar 进行线程安全的上下文管理
_task_context: ContextVar[TaskContext] = ContextVar("task_context", default=TaskContext())


def generate_task_id() -> str:
    """生成唯一的任务 ID"""
    return str(uuid.uuid4())


def set_task_context(
    task_id: Optional[str] = None,
    keyword: str = "",
    platform: str = "",
    target_keyword: str = "",
    user_id: str = "",
    **extra
) -> TaskContext:
    """
    设置当前任务的上下文

    Usage:
        set_task_context(task_id="xxx", keyword="李荣浩", platform="WB")
    """
    ctx = TaskContext(
        task_id=task_id or generate_task_id(),
        keyword=keyword,
        platform=platform,
        target_keyword=target_keyword,
        user_id=user_id,
        extra=extra,
    )
    _task_context.set(ctx)
    return ctx


def get_task_context() -> TaskContext:
    """获取当前任务的上下文"""
    return _task_context.get()


def update_task_context(**kwargs) -> TaskContext:
    """更新当前任务的上下文"""
    ctx = get_task_context()
    for key, value in kwargs.items():
        if hasattr(ctx, key):
            setattr(ctx, key, value)
        else:
            ctx.extra[key] = value
    _task_context.set(ctx)
    return ctx


def clear_task_context():
    """清除当前任务的上下文"""
    _task_context.set(TaskContext())


class TaskContextManager:
    """任务上下文管理器 - 用于 with 语句"""

    def __init__(
        self,
        task_id: Optional[str] = None,
        keyword: str = "",
        platform: str = "",
        **extra
    ):
        self.task_id = task_id or generate_task_id()
        self.keyword = keyword
        self.platform = platform
        self.extra = extra
        self._previous_ctx: Optional[TaskContext] = None

    def __enter__(self) -> "TaskContextManager":
        self._previous_ctx = get_task_context()
        set_task_context(
            task_id=self.task_id,
            keyword=self.keyword,
            platform=self.platform,
            **self.extra
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._previous_ctx:
            _task_context.set(self._previous_ctx)
        return False

    @property
    def context(self) -> TaskContext:
        return get_task_context()
