"""
WS3: 安全加固中间件

集中管理 FastAPI 应用的安全增强：
  - SecurityHeadersMiddleware: 注入安全响应头（CSP, HSTS, XFO 等）
  - MaxBodySizeMiddleware: 限制请求体大小
"""
import json
from typing import Callable, Awaitable
from fastapi import FastAPI, Request, Response
from core.logger import get_logger

logger = get_logger("core.security")


# ============================================================
# WS3.2: 安全响应头中间件
# ============================================================

SECURITY_HEADERS = {
    # 只允许同源加载资源（最严格的 CSP，API 服务无前端资源）
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",

    # 禁止被嵌入 iframe（防点击劫持）
    "X-Frame-Options": "DENY",

    # 禁止 MIME 类型嗅探（防 MIME 混淆攻击）
    "X-Content-Type-Options": "nosniff",

    # 启用浏览器 XSS 过滤器（已弃用但仍广泛支持）
    "X-XSS-Protection": "0",

    # 强制 HTTPS（生产环境有效，先发模式 1 年）
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",

    # 禁止自动检测 referrer
    "Referrer-Policy": "strict-origin-when-cross-origin",

    # 限制跨域打开窗口的能力
    "Cross-Origin-Opener-Policy": "same-origin",

    # 限制跨域资源嵌入
    "Cross-Origin-Resource-Policy": "same-origin",

    # 限制跨域打开窗口访问 window.opener
    "Cross-Origin-Embedder-Policy": "require-corp",

    # 禁止通过 HTTP Header 泄露服务器信息
    "Server": "",
}


def add_security_headers_middleware(app: FastAPI):
    """
    挂载安全响应头中间件并用默认值覆盖不安全响应头。
    """
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        response: Response = await call_next(request)

        for header_name, header_value in SECURITY_HEADERS.items():
            # 不覆盖已存在（允许显式覆盖）
            if header_name not in response.headers:
                response.headers[header_name] = header_value

        # 移除常见的服务器信息泄露头
        for header_to_remove in ("server", "x-powered-by"):
            if header_to_remove in response.headers:
                del response.headers[header_to_remove]

        return response

    logger.info("[SecurityMiddleware] 安全响应头中间件已挂载")


# ============================================================
# WS3.3: 请求体大小限制
# ============================================================

_MAX_BODY_SIZE = 1024 * 1024  # 1 MB

def add_max_body_size_middleware(app: FastAPI, max_size: int = _MAX_BODY_SIZE):
    """
    挂载请求体大小限制中间件。
    超过限制返回 413 Payload Too Large。
    """
    @app.middleware("http")
    async def max_body_size_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        # 只对 POST/PUT/PATCH 方法检查
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length", "0")
            try:
                if int(content_length) > max_size:
                    return Response(
                        status_code=413,
                        content=json.dumps({"code": 413, "msg": "请求体过大，上限 1MB", "data": None}),
                        media_type="application/json",
                    )
            except (ValueError, TypeError):
                pass  # 无 Content-Length 头的不拦截（由 Starlette 自行处理）

        return await call_next(request)

    logger.info(f"[SecurityMiddleware] 请求体大小限制中间件已挂载 (max={max_size} bytes)")
