# backend/services/agent_service/api.py
"""
Agent Chat API（v2.2 P1.10 接 auth + owner_id 注入）

变更要点：
- 所有端点都过 get_current_user，未登录 → 401
- chat 端点：把 owner_id 绑定到 contextvar，所有 @with_owner 工具自动拿到当前用户
- 流式响应里用 async wrapper set/reset contextvar，确保 yield 边界不漏 owner
- memory 端点 P1 仍是全局 session_id 视图，per-user 隔离待 P-future
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.auth_deps import get_current_user
from core.logger import get_logger

from .agent_core import chat_with_agent_stream
from .memory import AgentMemoryManager
from .tools import reset_current_owner, set_current_owner

logger = get_logger("agent.api")

router = APIRouter()

memory_manager = AgentMemoryManager()


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    session_id: Optional[str] = None


async def _stream_with_owner(
    owner_id: str,
    messages: List[Dict[str, str]],
    session_id: Optional[str],
):
    """包一层 async generator，进入时设 contextvar，退出时复位。
    _request 透传到 chat_with_agent_stream，便于工具拿到 owner_id + session_id。"""
    token = set_current_owner(owner_id)
    try:
        _request = {
            "owner_id": owner_id,
            "session_id": session_id,
        }
        async for chunk in chat_with_agent_stream(
            messages, session_id=session_id, _request=_request
        ):
            yield chunk
    finally:
        reset_current_owner(token)


@router.post("/api/agent/chat")
async def agent_chat_endpoint(
    request: ChatRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    SSE 流式对话（v2.2 P2：多事件协议）。
    - 需 Bearer token
    - owner_id 注入到 contextvar + _request，工具层双保险
    - 事件类型：text / tool_call / tool_progress / tool_result / error / done
    """
    owner_id = str(current_user["id"])
    session_id = request.session_id or None
    return StreamingResponse(
        _stream_with_owner(owner_id, request.messages, session_id),
        media_type="text/event-stream",
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
async def get_memory_stats(current_user: Dict = Depends(get_current_user)):
    """返回历史会话列表（前端侧边栏用）。P1 仍是全局视图，P-future 加 owner_id 过滤。"""
    try:
        sessions = memory_manager.store.get_all_sessions(limit=50, owner_id=str(current_user["id"]))
        return {
            "success": True,
            "data": {
                "sessions": sessions,
                "total": len(sessions),
            },
        }
    except Exception as e:
        logger.error(f"[memory_stats] {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/agent/memory/{session_id}")
async def get_session_memory(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """获取指定 session 的记忆详情（v2.2 P0#2：owner 隔离，越权读取返回空）"""
    try:
        owner_id = str(current_user["id"])
        summary = memory_manager.store.get_summary(session_id, owner_id=owner_id)
        entities = memory_manager.store.get_frequent_entities(session_id, owner_id, min_count=1)
        facts = memory_manager.store.get_valid_facts(session_id, owner_id)
        patterns = memory_manager.store.get_recent_patterns(session_id, owner_id, days=7)

        return {
            "success": True,
            "data": {
                "summary": summary,
                "entities": entities,
                "facts": facts,
                "patterns": patterns,
            },
        }
    except Exception as e:
        logger.error(f"[session_memory] {e}")
        return {"success": False, "error": str(e)}


@router.delete("/api/agent/memory/{session_id}")
async def clear_session_memory(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """清除指定 session 的所有记忆（v2.2 P0#2：owner 隔离，仅删自己的 session）"""
    try:
        owner_id = str(current_user["id"])
        deleted = memory_manager.delete_session(session_id, owner_id=owner_id)
        if deleted == 0:
            # 0 行被删：可能是该 session 不属于当前 owner，或不存在
            return {
                "success": False,
                "error": "session 不存在或不属于当前用户",
                "deleted": 0,
            }
        return {
            "success": True,
            "message": f"session {session_id} 的记忆已清除",
            "deleted": deleted,
        }
    except Exception as e:
        logger.error(f"[clear_memory] {e}")
        return {"success": False, "error": str(e)}
