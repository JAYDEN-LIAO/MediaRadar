"""
Abstract base class for tool adapters.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class AbstractToolAdapter(ABC):
    """工具适配器基类"""

    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        on_progress: Optional[Callable[[dict], None]] = None,
        _request: Optional[dict] = None,
    ) -> str:
        """异步执行工具，返回标准化 JSON 字符串

        - on_progress(partial)：流式工具通过此回调推送增量 partial
        - _request：请求上下文（owner_id / session_id / trace_id 等），
          工具函数可在签名里声明 `_request=None` 来获取
        """
        pass

    @abstractmethod
    def supports(self, tool_name: str) -> bool:
        """检查是否支持该工具"""
        pass
