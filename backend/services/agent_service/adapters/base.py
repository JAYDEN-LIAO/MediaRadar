"""
Abstract base class for tool adapters.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict

class AbstractToolAdapter(ABC):
    """工具适配器基类"""

    @abstractmethod
    async def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """异步执行工具，返回标准化 JSON 字符串（修复 #1.1：async 支持）"""
        pass

    @abstractmethod
    def supports(self, tool_name: str) -> bool:
        """检查是否支持该工具"""
        pass