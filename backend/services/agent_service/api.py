# backend/services/agent_service/api.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from .agent_core import chat_with_agent_stream
from .memory import AgentMemoryManager

router = APIRouter()

memory_manager = AgentMemoryManager()


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    session_id: Optional[str] = None


@router.post("/api/agent/chat")
async def agent_chat_endpoint(request: ChatRequest):
    """
    接收前端的小程序/Vue传来的对话历史，返回大模型的流式打字机效果 (SSE)
    支持 session_id 用于记忆管理
    """
    session_id = request.session_id or None
    return StreamingResponse(
        chat_with_agent_stream(request.messages, session_id=session_id),
        media_type="text/event-stream"
    )


# ==================== 记忆管理 API ====================

class ClearMemoryRequest(BaseModel):
    session_id: str


class MemoryResponse(BaseModel):
    session_id: str
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


@router.get("/api/agent/memory")
async def get_memory_stats():
    """
    查看当前记忆库统计状态
    """
    try:
        stats = memory_manager.get_stats()
        return {
            "success": True,
            "data": {
                "entity_memory_count": stats.get("entity_memory", 0),
                "fact_memory_count": stats.get("fact_memory", 0),
                "pattern_memory_count": stats.get("pattern_memory", 0),
                "conversation_summary_count": stats.get("conversation_summary", 0),
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/agent/memory/{session_id}")
async def get_session_memory(session_id: str):
    """
    获取指定 session 的记忆详情
    """
    try:
        summary = memory_manager.store.get_summary(session_id)
        entities = memory_manager.store.get_frequent_entities(session_id, min_count=1)
        facts = memory_manager.store.get_valid_facts(session_id)
        patterns = memory_manager.store.get_recent_patterns(session_id, days=7)

        return {
            "success": True,
            "data": {
                "summary": summary,
                "entities": entities,
                "facts": facts,
                "patterns": patterns
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/api/agent/memory/{session_id}")
async def clear_session_memory(session_id: str):
    """
    清除指定 session 的所有记忆
    """
    try:
        memory_manager.delete_session(session_id)
        return {
            "success": True,
            "message": f"session {session_id} 的记忆已清除"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
