# backend/services/radar_service/api.py
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from .db_manager import get_latest_results, get_system_settings, save_system_settings
from .main import api_start_task, RADAR_STATUS, reload_config
from typing import List

router = APIRouter()

# ============================================================
# MCP Server 健康检查（Task 4.3）
# ============================================================

@router.get("/api/mcp/health")
def mcp_health_check():
    """
    MCP Server 健康检查端点
    用于外部服务（如 MCP Server）探测 radar_service 是否可用
    """
    return {
        "status": "ok",
        "service": "radar_service",
        "radar_status": RADAR_STATUS.get("status_text", "idle"),
        "is_running": RADAR_STATUS.get("is_running", False)
    }

@router.post("/api/start_task")
def start_task(background_tasks: BackgroundTasks):
    success, msg = api_start_task(background_tasks)
    if success:
        return {"code": 200, "msg": msg}
    else:
        return {"code": 400, "msg": msg}

@router.get("/api/radar_status")
def get_radar_status():
    return {"code": 200, "data": RADAR_STATUS}

@router.get("/api/yq_list")
def get_yq_list():
    db_results = get_latest_results(limit=50)
    
    plat_name_map = {
        "wb": "微博",
        "xhs": "小红书",
        "bili": "B站",
        "zhihu": "知乎",
        "dy": "抖音",
        "ks": "快手",
        "tieba": "贴吧"
    }
    
    formatted_data = []
    for r in db_results:
        risk_level = str(r.get("risk_level", "")).lower()
        if "high" in risk_level or "高" in risk_level:
            sentiment, risk_text = "negative", "高风险"
        elif "low" in risk_level or "低" in risk_level:
            sentiment, risk_text = "positive", "低风险"
        else:
            sentiment, risk_text = "neutral", "中风险"
            
        raw_content = r.get("content")
        if not raw_content or str(raw_content).strip() == "":
            raw_content = r.get("title") or "暂无内容"
            
        display_report = raw_content if sentiment != "negative" else r.get("report", "")
        
        if len(display_report) > 80:
            display_report = display_report[:80] + "..."

        formatted_data.append({
            "id": r["post_id"],
            "platform": plat_name_map.get(r["platform"], str(r["platform"]).upper()),
            "sentiment": sentiment,
            "risk": risk_text,
            "keyword": r.get("keyword", "未知"), 
            "core_issue": r.get("core_issue", "无异常"), 
            "report": display_report,          
            "url": r.get("url", ""),           
            "create_time": r.get("publish_time") or r.get("create_time", "")
        })
        
    return {
        "code": 200,
        "msg": "成功",
        "data": formatted_data
    }

class SettingsRequest(BaseModel):
    keywords: list
    inactive_keywords: list = []
    platforms: list
    push_summary: bool
    push_time: str
    alert_negative: bool
    monitor_frequency: float

@router.get("/api/settings")
def api_get_settings():
    return {"code": 200, "data": get_system_settings()}

@router.post("/api/settings")
def api_save_settings(req: SettingsRequest):
    save_system_settings(req.model_dump())
    reload_config()
    return {"code": 200, "msg": "系统设置已更新并生效"}


# ============================================================
# Phase 6: 话题演化追踪 API
# ============================================================

@router.get("/api/topic_evolution")
def get_topic_evolution(keyword: str, topic_id: str = ""):
    """
    前端详情页调用此接口，获取指定话题的完整演化时间线。

    参数：
        keyword: 监控关键词（必填）
        topic_id: 话题唯一标识（可选，不传则按 keyword 检索最新话题）

    返回：
        {
            "is_new_topic": bool,
            "topic_id": str,
            "topic_name": str,
            "keyword": str,
            "evolution": {
                "total_scan_count": int,
                "total_post_count": int,
                "duration_days": int,
                "risk_evolution_path": str,   # "2 → 3 → 4"
                "current_risk_level": int,
                "evolution_signal": str,       # "escalating" / "stable" / "deescalating" / "unknown"
                "timeline": [...],
            }
        }
    """
    from .topic_tracker import get_topic_history

    if not keyword:
        return {"code": 400, "msg": "keyword 参数必填"}

    result = get_topic_history(topic_id=topic_id, keyword=keyword)
    return {"code": 200, "data": result}


@router.post("/api/topic_evolution/migrate_clusters")
def migrate_topic_clusters(limit: int = 1000):
    """
    将 ai_results 表中的历史数据，按 keyword 聚合后，
    批量生成 cluster_summary 并写入 topic_evolution 集合。

    用于初始化时一次性执行，或数据修复。

    参数：
        limit: 最多迁移多少条 ai_results（默认 1000）

    返回：
        {"migrated_topics": int, "total": int}
    """
    from .topic_tracker import migrate_topics_from_ai_results

    migrated, total = migrate_topics_from_ai_results(limit=limit)
    return {
        "code": 200,
        "msg": f"迁移完成，共处理 {total} 个话题簇，写入成功 {migrated} 个",
        "data": {"migrated_topics": migrated, "total": total},
    }


@router.get("/api/topic_stats")
def get_topic_stats(keyword: str = ""):
    """
    获取话题演化库的统计信息（可选，用于管理后台）。

    参数：
        keyword: 可选，按关键词过滤

    返回：
        {
            "total_topics": int,
            "escalating_count": int,   # 风险升级中的话题数
            "new_topics_7d": int,      # 近7天新增话题数
        }
    """
    from .vector_store import get_topic_collection_info

    try:
        info = get_topic_collection_info()
        vectors_count = getattr(info, "vectors_count", None) or getattr(info, "points_count", 0)
        return {
            "code": 200,
            "data": {
                "total_topics": vectors_count,
                "keyword": keyword or "全部",
            }
        }
    except Exception as e:
        return {"code": 500, "msg": f"获取统计失败: {str(e)}"}