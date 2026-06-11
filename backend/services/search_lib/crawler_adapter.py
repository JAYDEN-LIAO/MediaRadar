"""
crawler_adapter.py — 爬虫适配器

通过线程池 + subprocess.run 运行爬虫，彻底绕过 asyncio 事件循环类型限制
（SelectorEventLoop 不支持 create_subprocess_exec）。
"""
import asyncio
import concurrent.futures
import os
import subprocess
import sys
from typing import AsyncGenerator, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.logger import get_logger
from core.config import settings

logger = get_logger("search.crawler_adapter")

CRAWLER_DIR = os.path.join(BASE_DIR, "backend", "services", "crawler_service")
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

PLATFORM_TABLE_MAP = {
    "wb": "weibo_note", "xhs": "xhs_note", "bilibili": "bilibili_video",
    "bili": "bilibili_video", "zhihu": "zhihu_question",
    "dy": "douyin_aweme", "ks": "kuaishou_aweme", "tieba": "tieba_post",
}


def _read_latest_posts(platform: str, query: str, max_count: int = 10) -> list[dict]:
    """从爬虫 DB 读取指定平台的最新帖子"""
    table = PLATFORM_TABLE_MAP.get(platform)
    if not table:
        logger.warning(f"[CrawlerAdapter] 不支持的平台: {platform}")
        return []

    db_path = settings.CRAWLER_DB_PATH
    if not os.path.exists(db_path):
        logger.warning(f"[CrawlerAdapter] 爬虫 DB 不存在: {db_path}")
        return []

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info({table})")
        columns_info = cursor.fetchall()
        if not columns_info:
            conn.close()
            return []
        existing_columns = {col['name'] for col in columns_info}

        def find_col(candidates):
            for c in candidates:
                if c in existing_columns:
                    return c
            return None

        id_col = find_col(['note_id', 'aweme_id', 'tweet_id', 'id', 'item_id'])
        content_col = find_col(['desc', 'content', 'text', 'detail', 'article'])
        url_col = find_col(['note_url', 'url', 'video_url', 'article_url', 'link'])
        title_col = find_col(['title', 'name'])
        image_col = find_col(['image_list', 'pic_list', 'images', 'pics', 'image_url'])

        if not id_col or not content_col:
            conn.close()
            return []

        cols = [id_col, content_col]
        if url_col: cols.append(url_col)
        if title_col: cols.append(title_col)
        if image_col: cols.append(image_col)

        cols_str = ", ".join(cols)
        cursor.execute(f"SELECT {cols_str} FROM {table} ORDER BY ROWID DESC LIMIT ?", (max_count,))
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            post_id = str(r[id_col])
            content = r[content_col] or ""
            _title = (r[title_col] if title_col else "") or ""
            if query and query.lower() not in content.lower() and query.lower() not in _title.lower():
                continue

            image_urls = []
            if image_col and r[image_col]:
                val = str(r[image_col])
                if val.startswith('['):
                    try: image_urls = __import__('json').loads(val)
                    except: pass
                else:
                    image_urls = [u.strip() for u in val.split(',') if u.strip()]

            results.append({
                "post_id": post_id,
                "title": r[title_col] if title_col else "无标题",
                "content": content,
                "url": r[url_col] if url_col else "",
                "image_urls": image_urls,
                "platform": platform,
            })
        return results
    except Exception as e:
        logger.error(f"[CrawlerAdapter] 读取平台 {platform} 失败: {e}")
        return []


async def quick_crawl_stream(
    query: str,
    platforms: Optional[list[str]] = None,
    max_per_platform: int = 5,
) -> AsyncGenerator[dict, None]:
    """跨平台快速爬虫：线程池 subprocess.run，兼容所有事件循环类型"""
    if platforms is None:
        platforms = list(PLATFORM_TABLE_MAP.keys())

    loop = asyncio.get_running_loop()

    for plat in platforms:
        table = PLATFORM_TABLE_MAP.get(plat)
        if not table:
            continue

        logger.info(f"[CrawlerAdapter] 启动爬虫: platform={plat}, query={query}")
        cmd = [
            VENV_PYTHON, "main.py",
            "--platform", plat,
            "--type", "search",
            "--save_data_option", "sqlite",
            "--headless", "no",
            "--keywords", query,
        ]

        # Popen + 轮询：不阻塞事件循环，发送进度事件
        proc = subprocess.Popen(cmd, cwd=CRAWLER_DIR,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = loop.time() + 300
        try:
            while proc.poll() is None:
                await asyncio.sleep(1)
                if loop.time() > deadline:
                    proc.kill()
                    logger.warning(f"[CrawlerAdapter] {plat} 爬虫超时")
                    break
            if proc.returncode == 0 or proc.poll() is not None:
                logger.info(f"[CrawlerAdapter] {plat} 爬虫完成, returncode={proc.returncode}")
        except Exception as e:
            proc.kill()
            logger.error(f"[CrawlerAdapter] {plat} 爬虫异常 [{type(e).__name__}]: {e!r}")
            continue
        finally:
            try: proc.wait(timeout=5)
            except: proc.kill()

        if proc.returncode is None or proc.returncode != 0:
            continue

        # 读取结果
        posts = _read_latest_posts(plat, query, max_count=max_per_platform)
        yield {"type": "progress", "platform": plat, "scanned": len(posts)}
        for post in posts:
            yield {"type": "item", "item": post}

    logger.info("[CrawlerAdapter] 全平台搜索完成")
