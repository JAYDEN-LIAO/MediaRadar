"""
Direct tool adapter - 直接调用 tools.py 中的函数（无协议开销）。

v2.2 P2：新增 on_progress 回调和 _request 上下文注入。
- 工具函数如果声明 `on_progress=None` 参数，可调用它推 partial
- 工具函数如果声明 `_request=None` 参数，可拿到 {owner_id, session_id, ...}
- 未声明的参数会被 inspect 过滤掉，向后兼容
"""
import asyncio
import inspect
import json
from typing import Any, Callable, Dict, Optional

from .base import AbstractToolAdapter
from ..tools import AVAILABLE_TOOLS


def _accepted_kwargs(func, explicit: dict) -> dict:
    """只把函数签名里有的 kwargs 传进去；其余丢弃。"""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return explicit
    params = sig.parameters
    return {k: v for k, v in explicit.items() if k in params}


class DirectAdapter(AbstractToolAdapter):
    """直调 tools.py 的适配器（同时支持 sync / async 工具）"""

    def supports(self, tool_name: str) -> bool:
        return tool_name in AVAILABLE_TOOLS

    async def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        on_progress: Optional[Callable[[dict], None]] = None,
        _request: Optional[dict] = None,
    ) -> str:
        """
        异步执行 tools.py 中对应的函数。
        返回格式统一为：{"success": bool, "data": Any, "error": str, "error_type": str}
        """
        func = AVAILABLE_TOOLS.get(tool_name)
        if not func:
            return json.dumps({
                "success": False,
                "data": None,
                "error": f"Tool '{tool_name}' not found",
                "error_type": "unknown"
            }, ensure_ascii=False)

        # 注入上下文 kwargs（仅当函数接受时）
        ctx_kwargs = _accepted_kwargs(func, {
            "on_progress": on_progress,
            "_request": _request,
        })
        # 合并：args 在前，ctx 在后（args 不会覆盖 ctx，避免 LLM 伪造 _owner_id）
        merged = {**args, **ctx_kwargs}

        try:
            # 同时支持 sync / async / async generator
            if asyncio.iscoroutinefunction(func):
                result = await func(**merged)
            elif inspect.isasyncgenfunction(func):
                # 流式工具：async generator 逐 partial yield，最终 yield 字符串
                parts = []
                async for partial in func(**merged):
                    if on_progress is not None:
                        on_progress(partial)
                    parts.append(partial)
                result = parts[-1] if parts else ""
            else:
                result = func(**merged)

            # 解析后重新包装为统一格式
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict) and "success" in parsed:
                    return result
                return json.dumps({
                    "success": True,
                    "data": parsed,
                    "error": "",
                    "error_type": ""
                }, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                return json.dumps({
                    "success": True,
                    "data": result,
                    "error": "",
                    "error_type": ""
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "data": None,
                "error": str(e),
                "error_type": "unknown"
            }, ensure_ascii=False)
