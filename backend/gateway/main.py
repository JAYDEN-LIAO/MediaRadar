# backend/gateway/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
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
from services.auth_service.api import router as auth_router  # WS4: 多用户认证
from services.subscription_service.api import router as subscription_router  # v2.2: 订阅/模型/配额/admin

# 触发 agent_service 模块加载，确保其 Counter/Histogram 已注册到 prometheus 默认注册表
import services.agent_service.agent_core  # noqa: F401

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from core.config import settings
from core.logger import get_logger
from core.rate_limiter import add_rate_limiting_middleware
from core.security_middleware import (
    add_security_headers_middleware,
    add_max_body_size_middleware,
)
# v2.2: 触发订阅表初始化
import services.radar_service.db_manager  # noqa: F401  触发 init_radar_db
logger = get_logger("gateway")

app = FastAPI(
    title="MediaRadar 统一接口网关",
    version="2.0",
    description="基于微服务架构的全局 API 网关"
)

# 8.1 trace_id 中间件：每个请求生成/沿用 trace_id，注入 ContextVar，回写响应头
from core.context import set_trace_id, generate_trace_id, clear_trace_id


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """
    每个 HTTP 请求注入 trace_id：
      - 入：读 X-Trace-Id；没有则生成 uuid4().hex
      - 中：set ContextVar，使下游所有日志自动带上 trace_id
      - 出：响应头回写 X-Trace-Id，便于前端 / 日志聚合关联
    """
    incoming = request.headers.get("X-Trace-Id", "").strip()
    trace_id = incoming if incoming else generate_trace_id()
    set_trace_id(trace_id)
    try:
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
    finally:
        clear_trace_id()

# 修复 #1.3：CORS 错配（* + credentials=True 违反 CORS 规范）
# 按 ENV 区分：
#   dev  环境：allow_origins=["*"]，credentials=False（便于本地联调）
#   prod 环境：allow_origins 来自 ALLOWED_ORIGINS，credentials=True（精确控制）
if settings.ENV == "prod":
    _origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    if not _origins:
        logger.warning("[Gateway] ENV=prod 但 ALLOWED_ORIGINS 为空，将回退到 *（不安全）")
        _origins = ["*"]
    _credentials = True
else:
    _origins = ["*"]
    _credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WS3: 安全加固中间件（按顺序：限流 → 安全头 → 请求体大小）
add_rate_limiting_middleware(app)
add_security_headers_middleware(app)
add_max_body_size_middleware(app)

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
app.include_router(auth_router, tags=["WS4 用户认证"])
app.include_router(subscription_router, tags=["v2.2 订阅/模型/配额"])


@app.get("/metrics", tags=["可观测性"])
async def metrics():
    """Prometheus 指标暴露端点（7.2）"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def on_startup():
    """FastAPI 启动时自动启动定时调度器"""
    try:
        from services.radar_service.scheduler import scheduler_start
        success, msg = scheduler_start()
        logger.info(f"[Gateway] {msg}")
    except Exception as e:
        logger.warning(f"[Gateway] 调度器启动失败（不影响主服务）: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    """FastAPI 关闭时停止调度器"""
    try:
        from services.radar_service.scheduler import scheduler_stop
        success, msg = scheduler_stop()
        logger.info(f"[Gateway] {msg}")
    except Exception as e:
        logger.warning(f"[Gateway] 调度器关闭失败: {e}")
if __name__ == "__main__":
    # 启动命令说明：请在 backend 目录下执行 python gateway/main.py
    uvicorn.run("gateway.main:app", host="0.0.0.0", port=8008, reload=True)