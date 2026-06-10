"""
Tool registry + decorator + standard result shape.

每个工具用 `@tool(...)` 装饰即自动登记。聚合在 `tools/__init__.py` 暴露
为 TOOLS_SCHEMA / AVAILABLE_TOOLS / STREAMABLE_TOOLS。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from pydantic import BaseModel

# 全局注册表：name -> {func, schema, group, streamable}
_REGISTRY: dict[str, dict] = {}


def tool(
    name: str,
    *,
    description: str,
    parameters: Optional[dict] = None,
    group: str = "default",
    streamable: bool = False,
):
    """注册一个工具。

    Args:
        name: 工具名（LLM 看到的 function name）
        description: LLM 用来判断是否调用的描述（写清楚 "什么时候用我"）
        parameters: OpenAI Function Calling JSON Schema；无参数填 None
        group: 分组（subscription / scan / query / push / model / search / system）
        streamable: 是否是流式工具（async generator，主循环走 tool_progress 分支）
    """
    if name in _REGISTRY:
        raise ValueError(f"tool '{name}' already registered")

    def decorator(func: Callable):
        function_schema: dict = {
            "name": name,
            "description": description,
        }
        if parameters is not None:
            function_schema["parameters"] = parameters
        _REGISTRY[name] = {
            "func": func,
            "schema": {"type": "function", "function": function_schema},
            "group": group,
            "streamable": streamable,
        }
        # 把元数据贴到函数对象上，方便内省
        func._tool_name = name  # type: ignore[attr-defined]
        func._tool_group = group  # type: ignore[attr-defined]
        func._tool_streamable = streamable  # type: ignore[attr-defined]
        return func

    return decorator


def get_all_schemas() -> list[dict]:
    return [meta["schema"] for meta in _REGISTRY.values()]


def get_available_tools() -> dict[str, Callable]:
    return {name: meta["func"] for name, meta in _REGISTRY.items()}


def get_streamable_tools() -> set[str]:
    return {name for name, meta in _REGISTRY.items() if meta["streamable"]}


def get_tool(name: str) -> Optional[dict]:
    return _REGISTRY.get(name)


def list_tool_names_by_group() -> dict[str, list[str]]:
    by_group: dict[str, list[str]] = {}
    for name, meta in _REGISTRY.items():
        by_group.setdefault(meta["group"], []).append(name)
    return by_group


class ToolResult(BaseModel):
    """工具统一返回结构。前端按 ui.type 决定渲染哪个卡片。"""

    success: bool
    data: Any = None
    error: str = ""
    error_type: str = ""
    ui: Optional[dict] = None

    def to_json(self) -> str:
        return self.model_dump_json()
