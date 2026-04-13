# backend/services/agent_service/tools.py
import json
import threading
import time
from core.database import get_db_connection
from core.logger import get_logger
logger = get_logger("agent")
from services.radar_service.main import radar_status, job, MONITOR_KEYWORDS
import traceback
import asyncio

def tool_get_system_status() -> str:
    """获取雷达系统当前的运行状态"""
    try:
        data = radar_status.get_status_dict()
        return json.dumps({
            "success": True,
            "data": data,
            "error": "",
            "error_type": ""
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "data": None,
            "error": str(e),
            "error_type": "unknown"
        }, ensure_ascii=False)

def tool_trigger_background_crawl(keyword: str = None) -> str:
    """触发一次后台的全局数据抓取与分析任务"""
    if radar_status.is_running:
        return json.dumps({
            "success": False,
            "data": {"is_running": True},
            "error": "系统正在运行中，无需重复触发",
            "error_type": "param_error"
        }, ensure_ascii=False)

    current_keyword = "、".join(MONITOR_KEYWORDS) if MONITOR_KEYWORDS else "全局词库"
    target_msg = f"已收到专门针对【{keyword}】的探查请求，" if keyword else ""

    def _run():
        radar_status.set_running_sync(f"Agent 主动触发监控: {current_keyword}")
        try:
            logger.info(">>> 爬虫线程已启动，准备执行 job() <<<")
            new_count = job(keyword)
            if new_count is not None:
                radar_status.set_result_sync(new_count, time.strftime('%Y-%m-%d %H:%M:%S'))
            logger.info(">>> 爬虫线程 job() 执行完毕 <<<")
        except Exception as e:
            logger.error(f"❌ Agent 触发爬虫任务失败: {e}")
            logger.error(traceback.format_exc())
        finally:
            radar_status.set_idle_sync()

    threading.Thread(target=_run, daemon=True).start()

    return json.dumps({
        "success": True,
        "data": {"status": "started", "message": f"{target_msg}指令已下达，爬虫任务已在后台启动。"},
        "error": "",
        "error_type": ""
    }, ensure_ascii=False)

def tool_get_recent_alerts(limit: int = 5) -> str:
    """获取数据库中最近的高危（风险等级>=3）舆情警报列表"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, platform, keyword, risk_level, core_issue, report, publish_time
                FROM ai_results
                WHERE CAST(risk_level AS INTEGER) >= 3
                ORDER BY create_time DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

        if not rows:
            return json.dumps({
                "success": True,
                "data": [],
                "error": "",
                "error_type": ""
            }, ensure_ascii=False)

        results = []
        for r in rows:
            results.append({
                "title": r[0], "platform": r[1], "keyword": r[2],
                "risk_level": r[3], "core_issue": r[4], "report": r[5], "time": r[6]
            })
        return json.dumps({
            "success": True,
            "data": results,
            "error": "",
            "error_type": ""
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"DB Error in tool_get_recent_alerts: {e}")
        return json.dumps({
            "success": False,
            "data": None,
            "error": f"数据库查询失败: {str(e)}",
            "error_type": "data_empty"
        }, ensure_ascii=False)

# ---------------------------------------------------------
# OpenAI Function Calling 标准 Schema 定义
# ---------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "获取当前舆情雷达系统的运行状态（是否正在抓取、上次抓取时间等）。无参数。"
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_background_crawl",
            "description": "当用户要求立刻抓取最新数据、或去各大平台看看最新动态时调用此工具。它会在后台启动爬虫任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "用户想要抓取或关注的特定品牌/关键字（如'华为'）。如果没提具体品牌则不填。"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_alerts",
            "description": "获取数据库中最近的高危（风险等级>=3）舆情警报列表。当用户询问'最近有什么负面舆情'或'历史高危事件'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "要获取的记录条数，默认5"}
                }
            }
        }
    }
]

AVAILABLE_TOOLS = {
    "get_system_status": tool_get_system_status,
    "trigger_background_crawl": tool_trigger_background_crawl,
    "get_recent_alerts": tool_get_recent_alerts
}