# backend/gateway/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import traceback
import sys
import os

# 将 backend 目录动态加入系统路径，确保能够跨越子目录导入其他模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 按照新目录结构导入雷达业务模块的路由
from services.radar_service.api import router as radar_router
from services.agent_service.api import router as agent_router

try:
    from core.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("gateway")

app = FastAPI(
    title="MediaRadar 统一接口网关",
    version="2.0",
    description="基于微服务架构的全局 API 网关"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)
    logger.error(f"Global exception caught at {request.url}: {error_msg}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "系统内部处理异常", "data": None}
    )

# 挂载雷达业务子路由
# 注：为严格保持原有前端接口调用路径 (/api/...) 不变，此处暂不添加统一前缀
app.include_router(radar_router, tags=["舆情雷达业务层"])
app.include_router(agent_router, tags=["AI助手业务层"])
if __name__ == "__main__":
    # 启动命令说明：请在 backend 目录下执行 python gateway/main.py
    uvicorn.run("gateway.main:app", host="0.0.0.0", port=8008, reload=True)