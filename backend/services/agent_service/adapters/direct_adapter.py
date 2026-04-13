"""
Direct tool adapter - 直接调用 tools.py 中的函数（无协议开销）。
"""
import json
from typing import Any, Dict
from .base import AbstractToolAdapter
from ..tools import AVAILABLE_TOOLS

class DirectAdapter(AbstractToolAdapter):
    """直调 tools.py 的适配器"""

    def supports(self, tool_name: str) -> bool:
        return tool_name in AVAILABLE_TOOLS

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        直接调用 tools.py 中对应的函数。
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

        try:
            result = func(**args)
            # tools.py 目前返回的是 json.dumps 后的字符串
            # 解析后重新包装为统一格式
            try:
                parsed = json.loads(result)
                # 如果已经是 dict 且包含 success 字段，保持原样
                if isinstance(parsed, dict) and "success" in parsed:
                    return result
                # 否则包装
                return json.dumps({
                    "success": True,
                    "data": parsed,
                    "error": "",
                    "error_type": ""
                }, ensure_ascii=False)
            except json.JSONDecodeError:
                # 原始返回非 JSON 字符串
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