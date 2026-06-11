"""
Agent 工具集（v2.2，分组注册：订阅/扫描/查询/推送/模型/系统状态）。

每个模块用 `@tool(...)` 装饰函数即自动注册。本 __init__ 触发
所有模块导入，并把聚合后的 schema / 可调用映射 / 流式集合
暴露给上层（agent_core.py / adapters）。

【注意】新增工具组时记得在下面 import 段加一行 `from . import xxx`，
否则装饰器不会执行 → 工具不会注册。
"""
from __future__ import annotations

# === 触发各组工具注册（顺序无关，但全部要导入）===
# 已实现：system（G 组）+ subscription（A 组）
from . import system  # noqa: F401  G 组 系统状态
from . import subscription  # noqa: F401  A 组 订阅
from . import scan  # noqa: F401  B 组 扫描调度
from . import query  # noqa: F401  C 组 数据查询
from . import push  # noqa: F401  D 组 推送通道
from . import model  # noqa: F401  E 组 模型管理
from . import search  # noqa: F401  F 组 全网搜索

from ._base import (
    ToolResult,
    get_all_schemas,
    get_available_tools,
    get_streamable_tools,
    get_tool,
    list_tool_names_by_group,
    tool,
)
from ._owner import (
    OwnerRequiredError,
    get_current_owner,
    reset_current_owner,
    set_current_owner,
    with_owner,
)

# 兼容旧代码：保留 TOOLS_SCHEMA / AVAILABLE_TOOLS 这两个名字
# （agent_core.py / direct_adapter.py 都从这导入）
TOOLS_SCHEMA = get_all_schemas()
AVAILABLE_TOOLS = get_available_tools()
STREAMABLE_TOOLS = get_streamable_tools()

__all__ = [
    # 注册 / 反射
    "tool",
    "ToolResult",
    "get_all_schemas",
    "get_available_tools",
    "get_streamable_tools",
    "get_tool",
    "list_tool_names_by_group",
    # owner 上下文
    "set_current_owner",
    "reset_current_owner",
    "get_current_owner",
    "with_owner",
    "OwnerRequiredError",
    # 兼容旧名字
    "TOOLS_SCHEMA",
    "AVAILABLE_TOOLS",
    "STREAMABLE_TOOLS",
]
