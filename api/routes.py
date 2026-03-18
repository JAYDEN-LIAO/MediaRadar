from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os

# 确保能导入 yq_radar 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yq_radar.yq_main import api_start_task, RADAR_STATUS
from yq_radar.db_manager import get_latest_results

router = APIRouter()

class TaskRequest(BaseModel):
    keywords: list[str]

@router.get("/api/status")
async def get_status():
    """获取雷达当前运行状态"""
    return RADAR_STATUS

@router.post("/api/start")
async def start_radar(req: TaskRequest):
    """启动一次舆情雷达扫描"""
    success, msg = api_start_task(req.keywords)
    return {"success": success, "message": msg}

@router.get("/api/data/latest")
async def get_latest_data(limit: int = 20):
    """拉取最新的舆情分析结果列表"""
    data = get_latest_results(limit)
    return {"status": "success", "data": data}