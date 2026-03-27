# backend/services/agent_service/api.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from .agent_core import chat_with_agent_stream

# 专门针对 Agent 聊天的路由
router = APIRouter()

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]] 

@router.post("/api/agent/chat")
async def agent_chat_endpoint(request: ChatRequest):
    """
    接收前端的小程序/Vue传来的对话历史，返回大模型的流式打字机效果 (SSE)
    """
    return StreamingResponse(
        chat_with_agent_stream(request.messages), 
        media_type="text/event-stream"
    )