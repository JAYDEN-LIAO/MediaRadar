# backend/services/radar_service/db_manager.py
import sqlite3
import os
import json
import sys

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
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                config_json TEXT
            )
        ''')
        
        try:
            cursor.execute("ALTER TABLE ai_results ADD COLUMN title TEXT")
            cursor.execute("ALTER TABLE ai_results ADD COLUMN content TEXT")
            cursor.execute("ALTER TABLE ai_results ADD COLUMN url TEXT")
        except sqlite3.OperationalError:
            pass

def save_ai_result(post_id, platform, keyword, title, content, url, risk_level, core_issue, report):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ai_results 
            (post_id, platform, keyword, title, content, url, risk_level, core_issue, report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post_id, platform, keyword, title, content, url, risk_level, core_issue, report))

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

                unprocessed_posts.append({
                    "post_id": post_id,
                    "title": row[title_col] if title_col else "无标题",
                    "content": row[content_col] or "无正文",
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

init_radar_db()