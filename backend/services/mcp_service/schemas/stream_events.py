# backend/services/mcp_service/schemas/stream_events.py
"""
MCP Server 流式事件类型定义

LangGraph 分析类 Tool（analyze_cluster / run_full_pipeline）执行时间较长（30s-120s），
采用 SSE (Server-Sent Events) 流式输出进度和结果。

事件类型：
- screener_progress  — Screener 阶段进度
- cluster_progress   — 聚类阶段进度
- analysis_progress   — 分析节点进度 (analyst / reviewer / director)
- final_result        — 最终结果
- error               — 错误信息
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import json


# ============================================================
# 事件类型枚举
# ============================================================

class StreamEventType(str, Enum):
    SCREENER_PROGRESS = "screener_progress"     # Screener 阶段进度
    CLUSTER_PROGRESS = "cluster_progress"       # 聚类阶段进度
    ANALYSIS_PROGRESS = "analysis_progress"     # 分析节点进度
    FINAL_RESULT = "final_result"               # 最终结果
    ERROR = "error"                             # 错误信息
    COMPLETED = "completed"                     # 全部完成


# ============================================================
# 基础事件
# ============================================================

@dataclass
class StreamEvent:
    """流式事件基类"""
    event: str  # 事件类型
    data: Dict[str, Any]  # 事件数据

    def to_sse(self) -> str:
        """转换为 SSE 格式字符串"""
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        return {"event": self.event, **self.data}


# ============================================================
# 进度类事件
# ============================================================

@dataclass
class ScreenerProgressEvent(StreamEvent):
    """Screener 阶段进度"""
    def __init__(self, current: int, total: int, matched: int, message: str = ""):
        super().__init__(
            event=StreamEventType.SCREENER_PROGRESS.value,
            data={
                "current": current,
                "total": total,
                "matched": matched,
                "message": message or f"正在筛选... ({current}/{total})"
            }
        )


@dataclass
class ClusterProgressEvent(StreamEvent):
    """聚类阶段进度"""
    def __init__(self, current: int, total: int, topic: str = "", message: str = ""):
        super().__init__(
            event=StreamEventType.CLUSTER_PROGRESS.value,
            data={
                "current": current,
                "total": total,
                "topic": topic,
                "message": message or f"正在聚类话题... ({current}/{total})"
            }
        )


@dataclass
class AnalysisProgressEvent(StreamEvent):
    """分析节点进度"""
    def __init__(self, node: str, status: str, risk_level: int = 0, message: str = ""):
        """
        node: analyst | reviewer | director
        status: started | completed | skipped
        """
        node_messages = {
            "analyst": "DeepSeek 分析师正在评估风险...",
            "reviewer": "Kimi 复核员正在交叉验证...",
            "director": "Kimi 决策官正在生成预警简报..."
        }
        super().__init__(
            event=StreamEventType.ANALYSIS_PROGRESS.value,
            data={
                "node": node,
                "status": status,
                "risk_level": risk_level,
                "message": message or node_messages.get(node, f"{node} 节点执行中...")
            }
        )


# ============================================================
# 结果类事件
# ============================================================

@dataclass
class FinalResultEvent(StreamEvent):
    """最终结果事件"""
    def __init__(self, result: Dict[str, Any], topic_name: str = ""):
        super().__init__(
            event=StreamEventType.FINAL_RESULT.value,
            data={
                "result": result,
                "topic_name": topic_name,
                "message": f"分析完成：{topic_name or '话题'}"
            }
        )


@dataclass
class ErrorEvent(StreamEvent):
    """错误事件"""
    def __init__(self, error: str, stage: str = ""):
        super().__init__(
            event=StreamEventType.ERROR.value,
            data={
                "error": error,
                "stage": stage,
                "message": f"[{stage}] 出错: {error}" if stage else f"出错: {error}"
            }
        )


@dataclass
class CompletedEvent(StreamEvent):
    """全部完成事件"""
    def __init__(self, total_results: int = 0, message: str = ""):
        super().__init__(
            event=StreamEventType.COMPLETED.value,
            data={
                "total_results": total_results,
                "message": message or f"分析管线执行完毕，共产出 {total_results} 条结果"
            }
        )


# ============================================================
# SSE 辅助函数
# ============================================================

def sse_comment(message: str) -> str:
    """生成 SSE comment（保持连接存活）"""
    return f": {message}\n\n"


def sse_error(error: str, stage: str = "") -> str:
    """快捷生成 error 事件"""
    return ErrorEvent(error, stage).to_sse()


def sse_final_result(result: Dict[str, Any], topic_name: str = "") -> str:
    """快捷生成 final_result 事件"""
    return FinalResultEvent(result, topic_name).to_sse()


def sse_completed(total: int = 0) -> str:
    """快捷生成 completed 事件"""
    return CompletedEvent(total).to_sse()
