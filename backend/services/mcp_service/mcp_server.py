# backend/services/mcp_service/mcp_server.py
"""
MediaRadar MCP Server

舆情监控系统的 MCP Server 实现。
通过 FastMCP 提供 Tools 和 Resources，供 Claude Code 等 AI 客户端调用。

使用方式：
    # 本地 stdio 模式（Claude Code）
    python backend/services/mcp_service/mcp_server.py

    # HTTP 模式（云端部署）
    python backend/services/mcp_service/mcp_server.py --transport http
"""

from __future__ import annotations

import sys
import os
import asyncio
import argparse
import logging

# ============================================================
# 路径设置
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# ============================================================
# 日志配置
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("mcp_server")

# ============================================================
# 导入 MCP SDK
# ============================================================

from mcp.server import FastMCP

# ============================================================
# 导入各层模块
# ============================================================

from .tools.crawl_tools import register_crawl_tools
from .tools.pipeline_tools import register_pipeline_tools
from .tools.alert_tools import register_alert_tools
from .tools.config_tools import register_config_tools
from .resources.radar_resources import register_resources

# ============================================================
# Server 实例初始化
# ============================================================

mcp = FastMCP(
    name="MediaRadar",
    instructions=(
        "MediaRadar 舆情监控系统 MCP Server。\n\n"
        "支持功能：\n"
        "1. 多平台舆情爬取（微博/小红书/抖音/知乎/哔哩哔哩/快手/贴吧）\n"
        "2. AI 驱动的舆情分析（Screener → Vision → Cluster → LangGraph 分析）\n"
        "3. 风险预警与推送\n"
        "4. 监控配置管理\n\n"
        "典型对话场景：\n"
        "- '帮我查一下华为最近的舆情' → trigger crawl + analyze\n"
        "- '最近有哪些高危预警' → get_recent_alerts\n"
        "- '更新一下监控关键词' → update_keywords\n"
    ),
    log_level="INFO",
)

# ============================================================
# 注册 Tools
# ============================================================

logger.info("📦 注册 Crawl Tools...")
register_crawl_tools(mcp)

logger.info("📦 注册 Pipeline Tools...")
register_pipeline_tools(mcp)

logger.info("📦 注册 Alert Tools...")
register_alert_tools(mcp)

logger.info("📦 注册 Config Tools...")
register_config_tools(mcp)

# ============================================================
# 注册 Resources
# ============================================================

logger.info("📦 注册 Resources...")
register_resources(mcp)

# ============================================================
# 启动入口
# ============================================================

async def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="MediaRadar MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="传输模式：stdio（本地Claude Code用）/ http（云端部署用）"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP 模式监听地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="HTTP 模式监听端口"
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("🚀 启动 MCP Server（stdio 模式）...")
        await mcp.run_stdio_async()
    else:
        logger.info(f"🚀 启动 MCP Server（HTTP 模式，{args.host}:{args.port}）...")
        # HTTP 模式：挂载为 ASGI app
        app = mcp.streamable_http_app()
        import uvicorn
        config = uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Server 已关闭")
        sys.exit(0)
