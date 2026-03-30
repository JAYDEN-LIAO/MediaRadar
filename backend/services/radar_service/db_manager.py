# backend/services/radar_service/db_manager.py
import sqlite3
import os
import json
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.database import get_db_connection
from core.logger import logger
from core.config import settings

def init_radar_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_posts (
                post_id TEXT PRIMARY KEY,
                platform TEXT,
                process_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_results (
                post_id TEXT PRIMARY KEY,
                platform TEXT,
                keyword TEXT,
                title TEXT,
                content TEXT,
                url TEXT,
                risk_level TEXT,
                core_issue TEXT,
                report TEXT,
                publish_time TEXT,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                config_json TEXT
            )
        ''')

        # ── 话题聚合表（任务1）───────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_summary (
                topic_id TEXT PRIMARY KEY,
                keyword TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                cluster_summary TEXT,
                risk_level INTEGER DEFAULT 2,
                risk_class TEXT DEFAULT 'neutral',
                core_issue TEXT,
                report TEXT,
                first_seen TEXT,
                last_seen TEXT,
                post_count INTEGER DEFAULT 0,
                platforms TEXT DEFAULT '[]',
                sentiment TEXT DEFAULT 'neutral',
                scan_count INTEGER DEFAULT 1,
                is_processed INTEGER DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topic_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                add_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(topic_id, post_id)
            )
        ''')
        # ──────────────────────────────────────────────────────

        try:
            cursor.execute("ALTER TABLE ai_results ADD COLUMN publish_time TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE ai_results ADD COLUMN topic_id TEXT")
        except sqlite3.OperationalError:
            pass

def _async_index_to_qdrant(result: dict):
    """异步将 ai_results 写入 Qdrant（不阻塞主流程）"""
    try:
        from .vector_store import index_ai_result
        index_ai_result(result)
        logger.info(f"📚 [RAG Index] post_id={result['post_id']} 已写入 Qdrant")
    except Exception as e:
        logger.warning(f"⚠️ [RAG Index] 索引失败（不影响主流程）：{e}")


def save_ai_result(post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time="未知时间"):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ai_results
            (post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time))
        conn.commit()

    # ── 异步触发 RAG 索引（新增）───────────────────
    result_dict = {
        "post_id": post_id,
        "platform": platform,
        "keyword": keyword,
        "title": title,
        "content": content,
        "url": url,
        "risk_level": risk_level,
        "core_issue": core_issue,
        "report": report,
        "publish_time": publish_time,
    }
    threading.Thread(target=_async_index_to_qdrant, args=(result_dict,), daemon=True).start()
    # ───────────────────────────────────────────────

def get_latest_results(limit=50):
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
    return [dict(r) for r in rows]

def is_processed(post_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM processed_posts WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
    return result is not None

def mark_processed(post_id, platform):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO processed_posts (post_id, platform) VALUES (?, ?)', (post_id, platform))

def get_processed_status_batch(post_ids):
    if not post_ids:
        return set()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(post_ids))
        query = f"SELECT post_id FROM processed_posts WHERE post_id IN ({placeholders})"
        cursor.execute(query, tuple(post_ids))
        processed_ids = {row[0] for row in cursor.fetchall()} 
        
    return processed_ids

def mark_processed_batch(post_info_list):
    if not post_info_list:
        return
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(
                'INSERT OR IGNORE INTO processed_posts (post_id, platform) VALUES (?, ?)', 
                post_info_list
            )
        except sqlite3.Error as e:
            logger.error(f"Database batch insert failed: {e}")

def get_unprocessed_posts(crawler_db_path, platform):
    if not os.path.exists(crawler_db_path):
        logger.warning(f"Crawler database not found: {crawler_db_path}")
        return []

    conn = get_db_connection(db_path=crawler_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    unprocessed_posts = []
    
    platform_table_map = {
        "wb": "weibo_note",
        "xhs": "xhs_note",
        "bilibili": "bilibili_video", 
        "bili": "bilibili_video",      
        "zhihu": "zhihu_question",     
        "dy": "douyin_aweme",
        "ks": "kuaishou_aweme",
        "tieba": "tieba_post"
    }

    table_name = platform_table_map.get(platform)
    if not table_name:
        logger.warning(f"Unsupported platform type: {platform}")
        conn.close()
        return []

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        
        if not columns_info:
            return []
            
        existing_columns = [col['name'] for col in columns_info]
        
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
            return []

        query_cols = [id_col, content_col]
        if url_col: query_cols.append(url_col)
        if title_col: query_cols.append(title_col)
        if image_col: query_cols.append(image_col)
        
        query_cols_str = ", ".join(query_cols)

        cursor.execute(f'''
            SELECT {query_cols_str} 
            FROM {table_name} 
            ORDER BY ROWID DESC LIMIT 200
        ''')
        rows = cursor.fetchall()
        
        all_post_ids = [str(row[id_col]) for row in rows]
        processed_ids_set = get_processed_status_batch(all_post_ids)
        
        for row in rows:
            post_id = str(row[id_col])
            if post_id not in processed_ids_set:
                image_urls = []
                if image_col and row[image_col]:
                    val = str(row[image_col])
                    if val.startswith('['):
                        try:
                            image_urls = json.loads(val)
                        except:
                            pass
                    else:
                        image_urls = [u.strip() for u in val.split(',') if u.strip()]

                post_time = "未知时间"
                time_fields = ['time', 'create_time', 'add_ts', 'date']
                for field in time_fields:
                    if field in row.keys():
                        val = row[field]
                        if val:
                            # 处理 MediaCrawler 常见的13位或10位时间戳
                            if isinstance(val, (int, float)) or (isinstance(val, str) and str(val).isdigit()):
                                val_int = int(val)
                                if val_int > 1e11:  # 13位毫秒级时间戳
                                    val_int = val_int / 1000
                                import datetime
                                post_time = datetime.datetime.fromtimestamp(val_int).strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                post_time = str(val) # 如果已经是字符串日期，直接用
                            break

                unprocessed_posts.append({
                    "post_id": post_id,
                    "title": row[title_col] if title_col else "无标题",
                    "content": row[content_col] or "无正文",
                    "publish_time": post_time,
                    "url": row[url_col] if url_col else f"未知链接 ({post_id})",
                    "image_urls": image_urls, # 塞入提取好的图片列表
                    "platform": platform
                })
                
    except sqlite3.OperationalError as e:
        logger.error(f"Database read exception: {e}")
    finally:
        conn.close()
        
    return unprocessed_posts

def get_system_settings():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM system_settings WHERE id = 1")
        row = cursor.fetchone()
        
    if row:
        return json.loads(row[0])
    else:
        default_config = {
            "keywords": ["北京银行"],
            "platforms": ["wb", "xhs"],
            "push_summary": True,
            "push_time": "18:00",
            "alert_negative": True,
            "monitor_frequency": 1.0
        }
        save_system_settings(default_config)
        return default_config

def save_system_settings(config_dict):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO system_settings (id, config_json)
            VALUES (1, ?)
        ''', (json.dumps(config_dict),))


# ============================================================
# 话题聚合 CRUD（任务1）
# ============================================================

def create_or_update_topic_summary(
    topic_id: str,
    keyword: str,
    topic_name: str,
    cluster_summary: str = "",
    risk_level: int = 2,
    risk_class: str = "neutral",
    core_issue: str = "",
    report: str = "",
    platforms: list = None,
    sentiment: str = "neutral",
) -> bool:
    """
    创建或更新话题聚合记录。
    如果话题已存在（topic_id 相同），则合并（更新 post_count、scan_count、last_seen 等）。
    返回 True 表示新建，False 表示更新。
    """
    if platforms is None:
        platforms = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("SELECT topic_id FROM topic_summary WHERE topic_id = ?", (topic_id,))
        exists = cursor.fetchone() is not None

        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        platforms_json = json.dumps(platforms)

        if exists:
            # 更新：累加 post_count、scan_count，更新 last_seen
            cursor.execute('''
                UPDATE topic_summary SET
                    cluster_summary = COALESCE(NULLIF(?, ''), cluster_summary),
                    risk_level = MAX(risk_level, ?),
                    risk_class = CASE
                        WHEN ? > risk_level THEN ?
                        ELSE risk_class
                    END,
                    core_issue = COALESCE(NULLIF(?, ''), core_issue),
                    report = COALESCE(NULLIF(?, ''), report),
                    platforms = ?,
                    sentiment = CASE
                        WHEN ? > risk_level THEN ?
                        ELSE sentiment
                    END,
                    scan_count = scan_count + 1,
                    last_seen = ?,
                    post_count = (
                        SELECT COUNT(*) FROM topic_posts WHERE topic_id = ?
                    )
                WHERE topic_id = ?
            ''', (
                cluster_summary, risk_level, risk_level, risk_class,
                core_issue, report,
                platforms_json,
                risk_level, sentiment,
                now, topic_id, topic_id
            ))
            conn.commit()
            return False
        else:
            # 新建
            cursor.execute('''
                INSERT INTO topic_summary
                (topic_id, keyword, topic_name, cluster_summary, risk_level, risk_class,
                 core_issue, report, platforms, sentiment, first_seen, last_seen, post_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                topic_id, keyword, topic_name, cluster_summary, risk_level, risk_class,
                core_issue, report, platforms_json, sentiment, now, now, 0
            ))
            conn.commit()
            return True


def add_post_to_topic(topic_id: str, post_id: str, is_current: int = 1):
    """将帖子关联到话题"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO topic_posts (topic_id, post_id, is_current)
            VALUES (?, ?, ?)
        ''', (topic_id, post_id, is_current))

        # 更新 ai_results 的 topic_id
        cursor.execute('''
            UPDATE ai_results SET topic_id = ?
            WHERE post_id = ?
        ''', (topic_id, post_id))

        # 更新 topic_summary 的 post_count
        cursor.execute('''
            UPDATE topic_summary SET post_count = (
                SELECT COUNT(*) FROM topic_posts WHERE topic_id = ?
            )
            WHERE topic_id = ?
        ''', (topic_id, topic_id))
        conn.commit()


def get_topic_summary_list(
    keyword: str = None,
    platform: str = None,
    sentiment: str = None,
    is_processed: int = None,
    limit: int = 50,
) -> list:
    """获取话题聚合列表（支持筛选）"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM topic_summary WHERE 1=1"
        params = []

        if keyword:
            query += " AND keyword = ?"
            params.append(keyword)

        if sentiment:
            query += " AND risk_class = ?"
            params.append(sentiment)

        if is_processed is not None:
            query += " AND is_processed = ?"
            params.append(is_processed)

        query += " ORDER BY last_seen DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    results = []
    for r in rows:
        d = dict(r)
        # platforms JSON → list
        try:
            d["platforms"] = json.loads(d.get("platforms", "[]"))
        except:
            d["platforms"] = []

        # 平台筛选（如果指定了 platform）
        if platform:
            # platforms 存的是 ["微博", "小红书"]，需要匹配
            plat_map = {"wb": "微博", "xhs": "小红书", "bili": "B站", "zhihu": "知乎", "dy": "抖音", "ks": "快手", "tieba": "贴吧"}
            target = plat_map.get(platform, platform)
            if target not in d["platforms"]:
                continue

        # 转换 risk_class → 中文 sentiment
        risk_class = d.get("risk_class", "neutral")
        sentiment_map = {"negative": "负面", "positive": "正面", "neutral": "中性"}
        d["sentiment"] = sentiment_map.get(risk_class, "中性")

        # 演化信号（暂无，从 topic_tracker 获取）
        d["evolution_signal"] = "unknown"

        results.append(d)

    return results


def get_topic_summary_by_id(topic_id: str) -> dict:
    """获取单个话题聚合详情"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topic_summary WHERE topic_id = ?", (topic_id,))
        row = cursor.fetchone()

    if not row:
        return None

    d = dict(row)
    try:
        d["platforms"] = json.loads(d.get("platforms", "[]"))
    except:
        d["platforms"] = []

    risk_class = d.get("risk_class", "neutral")
    sentiment_map = {"negative": "负面", "positive": "正面", "neutral": "中性"}
    d["sentiment"] = sentiment_map.get(risk_class, "中性")

    return d


def get_topic_posts(topic_id: str) -> list:
    """获取话题关联的所有帖子详情"""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ar.* FROM topic_posts tp
            JOIN ai_results ar ON ar.post_id = tp.post_id
            WHERE tp.topic_id = ?
            ORDER BY tp.is_current DESC, ar.create_time DESC
        ''', (topic_id,))
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def mark_topic_processed(topic_id: str) -> bool:
    """标记话题为已处理"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE topic_summary SET is_processed = 1 WHERE topic_id = ?",
            (topic_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


init_radar_db()