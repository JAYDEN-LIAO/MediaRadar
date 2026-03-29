# backend/services/mcp_service/adapter/crawler_adapter.py
"""
CrawlerAdapter: MCP Server 与 crawler_service 的适配层

职责：
- 对 crawler_service 的爬虫管理做薄封装
- 封装 asyncio 调用为同步/线程安全接口（供 MCP Tool 调用）
- 隔离 MCP Server 与 crawler_service 的直接依赖
"""

from __future__ import annotations
import sys
import os
import asyncio
import threading
from typing import Optional, Dict, Any, List

# ============================================================
# 路径设置（确保能导入 crawler_service）
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import logger

# ============================================================
# 导入 crawler_service 核心模块
# ============================================================

from services.crawler_service.api.schemas.crawler import (
    CrawlerStartRequest,
    CrawlerStatusResponse,
    PlatformEnum,
    CrawlerTypeEnum,
    LoginTypeEnum,
    SaveDataOptionEnum,
)
from services.crawler_service.api.services.crawler_manager import crawler_manager

# ============================================================
# 内部状态
# ============================================================

# MCP Server 侧维护的爬虫运行状态（与 crawler_manager 同步）
_crawl_status_cache: Dict[str, Any] = {
    "is_running": False,
    "status": "idle",
    "platform": None,
    "started_at": None,
    "task_id": None
}

# 锁（确保并发安全）
_crawl_lock = threading.Lock()


# ============================================================
# CrawlerAdapter
# ============================================================

class CrawlerAdapter:
    """
    crawler_service 适配器

    crawler_manager 是 asyncio 实现，MCP Tool 可能在同步上下文中调用。
    此类通过 run_in_executor / asyncio.run 封装为线程安全接口。
    """

    # 平台枚举（与 radar_adapter 保持一致）
    PLATFORMS = ["wb", "xhs", "bili", "zhihu", "dy", "ks", "tieba"]

    @classmethod
    def _get_event_loop(cls) -> asyncio.AbstractEventLoop:
        """获取或创建事件循环（线程安全）"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop

    @classmethod
    def _run_async(cls, coro):
        """在线程池中运行协程（同步上下文调用 asyncio 的桥接）"""
        loop = cls._get_event_loop()
        if threading.current_thread() == threading.main_thread():
            # 主线程：可以直接 run
            try:
                asyncio.get_running_loop()
                # 已在事件循环中，用 run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            except RuntimeError:
                return asyncio.run(coro)
        else:
            # 子线程：通过 run_in_executor
            future = asyncio.run(coro)
            return future

    # ============================================================
    # 爬虫控制
    # ============================================================

    @classmethod
    def start_crawl(
        cls,
        platform: str,
        keyword: Optional[str] = None,
        login_type: str = "qrcode",
        headless: bool = False
    ) -> Dict[str, Any]:
        """
        启动爬虫任务
        对应 Tool: crawl_platform

        参数：
            platform: 平台标识（wb/xhs/bili/zhihu/dy/ks/tieba）
            keyword: 搜索关键词（可选，不填则用系统配置的全局关键词）
            login_type: 登录方式（qrcode/phone/cookie）
            headless: 是否无头模式（False=显示浏览器）

        返回：
            {"success": bool, "message": str, "task_id": str}
        """
        with _crawl_lock:
            # 检查是否已在运行
            status = cls.get_crawl_status()
            if status["is_running"]:
                return {
                    "success": False,
                    "message": f"爬虫已在运行中（平台: {status['platform']}），请先停止",
                    "is_running": True
                }

            # 构造请求
            try:
                platform_enum = PlatformEnum(platform.lower())
            except ValueError:
                return {
                    "success": False,
                    "message": f"不支持的平台: {platform}，支持: {cls.PLATFORMS}"
                }

            try:
                login_enum = LoginTypeEnum(login_type.lower())
            except ValueError:
                login_enum = LoginTypeEnum.QRCODE

            config = CrawlerStartRequest(
                platform=platform_enum,
                login_type=login_enum,
                crawler_type=CrawlerTypeEnum.SEARCH,
                keywords=keyword or "",
                save_option=SaveDataOptionEnum.SQLITE,
                cookies="",
                headless=headless,
                enable_comments=True,
                enable_sub_comments=False,
            )

            # 异步启动
            async def _start():
                return await crawler_manager.start(config)

            try:
                success = asyncio.run(_start())
            except Exception as e:
                logger.error(f"❌ 启动爬虫失败: {e}")
                return {"success": False, "message": f"启动失败: {e}"}

            if not success:
                # 可能是已经在运行
                status = crawler_manager.get_status()
                if status.get("status") == "running":
                    return {
                        "success": False,
                        "message": "爬虫已在运行中，请勿重复启动",
                        "is_running": True
                    }
                return {"success": False, "message": "启动失败，请检查配置"}

            # 更新缓存
            _crawl_status_cache["is_running"] = True
            _crawl_status_cache["status"] = "running"
            _crawl_status_cache["platform"] = platform
            _crawl_status_cache["task_id"] = f"crawl_{platform}_{int(asyncio.get_event_loop().time() * 1000)}"

            return {
                "success": True,
                "message": f"爬虫已启动（平台: {platform}，关键词: {keyword or '全局'}）",
                "task_id": _crawl_status_cache["task_id"],
                "is_running": True
            }

    @classmethod
    def start_crawl_all(
        cls,
        keyword: Optional[str] = None,
        headless: bool = False
    ) -> Dict[str, Any]:
        """
        启动全平台爬虫（顺序执行）
        对应 Tool: crawl_all_platforms

        注意：这是同步接口，调用后立即返回（后台执行）
        """
        results = []
        for platform in cls.PLATFORMS:
            result = cls.start_crawl(platform=platform, keyword=keyword, headless=headless)
            results.append({
                "platform": platform,
                **result
            })

        return {
            "success": True,
            "message": f"全平台爬虫任务已下发（共 {len(cls.PLATFORMS)} 个平台）",
            "platforms": [r["platform"] for r in results],
            "details": results
        }

    @classmethod
    def stop_crawl(cls) -> Dict[str, Any]:
        """
        停止爬虫任务
        对应 Tool: stop_crawl
        """
        async def _stop():
            return await crawler_manager.stop()

        try:
            success = asyncio.run(_stop())
        except Exception as e:
            logger.error(f"❌ 停止爬虫失败: {e}")
            return {"success": False, "message": f"停止失败: {e}"}

        if success:
            _crawl_status_cache["is_running"] = False
            _crawl_status_cache["status"] = "idle"
            _crawl_status_cache["platform"] = None

        return {
            "success": success,
            "message": "爬虫已停止" if success else "停止失败或爬虫未在运行"
        }

    @classmethod
    def get_crawl_status(cls) -> Dict[str, Any]:
        """
        获取爬虫运行状态
        对应 Tool: get_crawler_status
        """
        try:
            raw_status = crawler_manager.get_status()
            manager_status = raw_status.get("status", "idle")
            is_running = manager_status in ("running", "stopping")
        except Exception as e:
            logger.error(f"获取爬虫状态失败: {e}")
            raw_status = {}
            manager_status = "error"
            is_running = False

        return {
            "is_running": is_running,
            "status": manager_status,
            "platform": raw_status.get("platform"),
            "crawler_type": raw_status.get("crawler_type"),
            "started_at": raw_status.get("started_at")
        }

    @classmethod
    def get_crawl_logs(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取爬虫运行日志
        对应 Resource / Tool: get_crawl_logs

        注意：crawler_manager.logs 同步访问可能有竞态，
        这里做一次浅拷贝保证返回数据一致性
        """
        try:
            logs = crawler_manager.logs
            # 浅拷贝防止迭代时修改
            return [
                {
                    "id": log.id,
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message
                }
                for log in logs[-limit:]
            ]
        except Exception as e:
            logger.error(f"获取爬虫日志失败: {e}")
            return []

    @classmethod
    def is_available(cls) -> bool:
        """检查 crawler_service 是否可用"""
        try:
            crawler_manager.get_status()
            return True
        except Exception:
            return False
