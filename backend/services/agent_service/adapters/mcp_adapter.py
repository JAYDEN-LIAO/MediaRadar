"""
MCP Adapter - 通过 HTTP transport 调用 FastMCP Server。

注意：同进程内调用应使用 HTTP transport（mcp.streamable_http_app），
不适用 stdio 模式（stdio 是 Claude Code CLI 子进程模式）。
"""
import json
import httpx
from typing import Any, Dict
from .base import AbstractToolAdapter

class MCPAdapter(AbstractToolAdapter):
    """MCP 协议适配器（HTTP transport）"""

    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url.rstrip("/")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client

    def supports(self, tool_name: str) -> bool:
        # MCP Adapter 理论上支持所有 MCP Server 注册的工具
        # 此处返回 True，由 MCP Server 实际判断
        return True

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        通过 HTTP 调用 MCP Server 的 /tools/call 接口。
        返回标准化 ToolResult 格式。
        """
        payload = {
            "name": tool_name,
            "arguments": args
        }

        try:
            response = self.client.post(
                f"{self.base_url}/v1/tools/call",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

            # MCP Server 返回格式：{content: [...], isError: bool}
            # 标准化为 {success, data, error, error_type}
            if result.get("isError"):
                return json.dumps({
                    "success": False,
                    "data": None,
                    "error": str(result.get("content", "")),
                    "error_type": "unknown"
                }, ensure_ascii=False)

            # 提取 content
            content_list = result.get("content", [])
            if content_list and isinstance(content_list, list):
                data = content_list[0].get("text", "") if "text" in content_list[0] else content_list[0]
                # 尝试解析为 JSON
                try:
                    parsed = json.loads(data)
                    return json.dumps({
                        "success": True,
                        "data": parsed,
                        "error": "",
                        "error_type": ""
                    }, ensure_ascii=False)
                except json.JSONDecodeError:
                    return json.dumps({
                        "success": True,
                        "data": data,
                        "error": "",
                        "error_type": ""
                    }, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "data": result,
                "error": "",
                "error_type": ""
            }, ensure_ascii=False)

        except httpx.TimeoutException:
            return json.dumps({
                "success": False,
                "data": None,
                "error": "MCP Server 请求超时",
                "error_type": "timeout"
            }, ensure_ascii=False)
        except httpx.ConnectError:
            return json.dumps({
                "success": False,
                "data": None,
                "error": "无法连接 MCP Server",
                "error_type": "network"
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "data": None,
                "error": str(e),
                "error_type": "unknown"
            }, ensure_ascii=False)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None