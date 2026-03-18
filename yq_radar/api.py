from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import sqlite3
import os
from yq_main import api_start_task, RADAR_STATUS
# 【新增这一行】：引入数据库查询方法
from db_manager import get_latest_results

# 引入你写好的核心调度函数和状态
from yq_main import api_start_task, RADAR_STATUS

app = FastAPI()

# 允许跨域请求（前端联调必备）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义前端传过来的数据格式
class TaskRequest(BaseModel):
    keyword: str

# 1. 启动雷达的接口
@app.post("/api/start_task")
def start_task(req: TaskRequest):
    # 调用 yq_main.py 里的函数，传入关键词
    success, msg = api_start_task([req.keyword])
    if success:
        return {"code": 200, "msg": msg}
    else:
        return {"code": 400, "msg": msg}

# 2. 查询雷达运行状态的接口（供前端展示“雷达运行中”）
@app.get("/api/radar_status")
def get_radar_status():
    return {"code": 200, "data": RADAR_STATUS}

# 3. 获取舆情列表的接口（稍后我们会换成查真实数据库）
# 3. 获取舆情列表的接口（查真实数据库！）
@app.get("/api/yq_list")
def get_yq_list():
    # 调用 db_manager 里的方法，拉取最新 20 条 AI 研判结果
    db_results = get_latest_results(limit=20)
    
    formatted_data = []
    for r in db_results:
        # 将后端的大模型 risk_level 转换为前端能识别的样式和颜色
        risk_level = str(r.get("risk_level", "")).lower()
        if "high" in risk_level or "高" in risk_level:
            sentiment, risk_text = "negative", "高风险"
        elif "low" in risk_level or "低" in risk_level:
            sentiment, risk_text = "positive", "低风险"
        else:
            sentiment, risk_text = "neutral", "中风险"
            
        # 如果是安全数据（正向/中性），让它展示帖子原文（content）；
        # 如果是高风险负面，展示 AI 提炼的深入研判报告（report）。
        display_report = r["content"] if sentiment != "negative" else r["report"]
        
        # 截取一下正文字数，防止列表撑得太长（最多显示80字）
        if len(display_report) > 80:
            display_report = display_report[:80] + "..."

        formatted_data.append({
            "id": r["post_id"],
            "platform": "微博" if r["platform"] == "wb" else "小红书",
            "sentiment": sentiment,
            "risk": risk_text,
            "keyword": r.get("keyword", "未知"), # 传给前端的弹窗筛选用
            "core_issue": r["core_issue"], 
            "report": display_report,          # <--- 这里用上了魔法变量
            "url": r.get("url", ""),           # 顺便把原始链接发给前端，以后做"查看详情"跳转用
            "create_time": r["create_time"]
        })
        
    return {
        "code": 200,
        "msg": "成功",
        "data": formatted_data
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)