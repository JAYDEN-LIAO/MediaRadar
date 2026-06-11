"""
SSE 事件工厂（v2.2 P2）

所有 chat_with_agent_stream 输出的事件都通过本模块构造，
保证前端 EventSource 解析稳定（event:/data: 双行 + 双换行收尾）。

事件清单：
  - text           LLM 流式文本片段
  - tool_call      LLM 决定调工具，开始执行前
  - tool_progress  流式工具的增量 partial
  - tool_result    工具完成（流式工具最后一次 partial 也是 result）
  - error          工具或主循环异常
  - done           当前回复结束

每个 emit 返回一个可直接 yield 的字符串。
"""
from __future__ import annotations

import json
from typing import Any, Optional


def _escape_data(s: str) -> str:
    """SSE 规范：data 字段里换行要用 \n 转义，否则会被当事件结束。
    但本协议约定 data 是单行 JSON（除 text 外）；这里为 text 留 raw 接口。"""
    return s.replace("\r\n", "\n")


def emit(event: str, data: Any = "", raw_data: bool = False) -> str:
    """通用 emit。raw_data=True 时 data 是已格式化好的字符串（不走 json.dumps）。"""
    if raw_data:
        payload = _escape_data(data) if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    else:
        payload = json.dumps(data, ensure_ascii=False) if data != "" and data is not None else ""
    return f"event: {event}\ndata: {payload}\n\n"


def emit_text(text: str) -> str:
    """LLM 文本流片段。data 字段 JSON 编码（避免换行打乱 SSE 帧），
    前端用 JSON.parse(e.data) 还原。"""
    if not text:
        return ""
    return f"event: text\ndata: {json.dumps(text, ensure_ascii=False)}\n\n"


def emit_tool_call(call_id: str, tool: str, args: dict) -> str:
    return emit("tool_call", {"call_id": call_id, "tool": tool, "args": args})


def emit_tool_progress(call_id: str, partial: dict) -> str:
    return emit("tool_progress", {"call_id": call_id, "partial": partial})


def emit_tool_result(
    call_id: str,
    success: bool,
    data: Any = None,
    ui: Optional[dict] = None,
    error: str = "",
    error_type: str = "",
) -> str:
    return emit("tool_result", {
        "call_id": call_id,
        "success": success,
        "data": data,
        "ui": ui or {},
        "error": error,
        "error_type": error_type,
    })


def emit_error(message: str, error_type: str = "unknown", call_id: Optional[str] = None) -> str:
    payload = {"message": message, "error_type": error_type}
    if call_id:
        payload["call_id"] = call_id
    return emit("error", payload)


def emit_done() -> str:
    return "event: done\ndata:\n\n"
