# yq_radar/api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from db_manager import get_latest_results, get_system_settings, save_system_settings
from yq_main import api_start_task, RADAR_STATUS, reload_config

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    keyword: str

@app.post("/api/start_task")
def start_task(req: TaskRequest):
    success, msg = api_start_task([req.keyword])
    if success:
        return {"code": 200, "msg": msg}
    else:
        return {"code": 400, "msg": msg}

@app.get("/api/radar_status")
def get_radar_status():
    return {"code": 200, "data": RADAR_STATUS}

# 3. 规范读取：直接从我们统一梳理好的 ai_results 库里读数据！
@app.get("/api/yq_list")
def get_yq_list():
    # 调用 db_manager 取出最新的 50 条入库数据
    db_results = get_latest_results(limit=50)
    
    formatted_data = []
    for r in db_results:
        risk_level = str(r.get("risk_level", "")).lower()
        if "high" in risk_level or "高" in risk_level:
            sentiment, risk_text = "negative", "高风险"
        elif "low" in risk_level or "低" in risk_level:
            sentiment, risk_text = "positive", "低风险"
        else:
            sentiment, risk_text = "neutral", "中风险"
            
        # 提取真实发帖内容，如果内容为空就取标题
        raw_content = r.get("content")
        if not raw_content or str(raw_content).strip() == "":
            raw_content = r.get("title") or "暂无内容"
            
        # 魔法呈现：正常报道显示网友/媒体原话，负面事件显示 AI 深度研判报告
        display_report = raw_content if sentiment != "negative" else r.get("report", "")
        
        if len(display_report) > 80:
            display_report = display_report[:80] + "..."

        formatted_data.append({
            "id": r["post_id"],
            "platform": "微博" if r["platform"] == "wb" else "小红书",
            "sentiment": sentiment,
            "risk": risk_text,
            "keyword": r.get("keyword", "未知"), 
            "core_issue": r.get("core_issue", "无异常"), 
            "report": display_report,          
            "url": r.get("url", ""),           
            "create_time": r.get("create_time", "")
        })
        
    return {
        "code": 200,
        "msg": "成功",
        "data": formatted_data
    }


# 定义前端传过来的设置格式
class SettingsRequest(BaseModel):
    keywords: list
    platforms: list
    push_summary: bool
    push_time: str
    alert_negative: bool
    monitor_frequency: float

# --- 新增的设置接口 ---
@app.get("/api/settings")
def api_get_settings():
    return {"code": 200, "data": get_system_settings()}

@app.post("/api/settings")
def api_save_settings(req: SettingsRequest):
    # 保存进数据库
    save_system_settings(req.model_dump())
    # 💥 魔法：通知核心系统立刻重新加载配置！
    reload_config()
    return {"code": 200, "msg": "系统设置已更新并生效！"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)