# backend/services/radar_service/db_manager.py
import sqlite3
import os
import json
import sys
import threading
from datetime import datetime
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.database import get_db_connection
from core.logger import get_logger

logger = get_logger("radar.db")
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

        # ── 审计日志表（修复 #7.1）───────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                keyword TEXT,
                topic_id TEXT,
                risk_level INTEGER DEFAULT 0,
                level TEXT DEFAULT 'INFO',
                detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
                ON audit_log(created_at)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_audit_log_action
                ON audit_log(action)
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
                alert_recommendation TEXT DEFAULT 'none',
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

        try:
            cursor.execute("ALTER TABLE ai_results ADD COLUMN sentiment TEXT DEFAULT 'Neutral'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE ai_results ADD COLUMN email_html TEXT")
        except sqlite3.OperationalError:
            pass

        # 话题表新增字段（存量数据库迁移）
        try:
            cursor.execute("ALTER TABLE topic_summary ADD COLUMN alert_recommendation TEXT DEFAULT 'none'")
        except sqlite3.OperationalError:
            pass

        # 7.1：审计日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                keyword TEXT,
                topic_id TEXT,
                risk_level INTEGER DEFAULT 0,
                detail TEXT,
                level TEXT DEFAULT 'INFO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC)')

        # v2.2: audit_log 加 owner_id 列（幂等迁移，旧记录为空串=系统级事件）
        try:
            cursor.execute("ALTER TABLE audit_log ADD COLUMN owner_id TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_audit_log_owner ON audit_log(owner_id)'
        )

        # ── WS4.6：数据隔离 owner_id 迁移（幂等）────────────────────
        # 旧数据 owner_id = NULL（公共/历史数据，所有用户可见）
        for alter_sql in [
            "ALTER TABLE ai_results ADD COLUMN owner_id TEXT",
            "ALTER TABLE topic_summary ADD COLUMN owner_id TEXT",
        ]:
            try:
                cursor.execute(alter_sql)
            except sqlite3.OperationalError:
                pass
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_results_owner_id ON ai_results(owner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_topic_summary_owner_id ON topic_summary(owner_id)')
        # ────────────────────────────────────────────────────────────

        # ── v2.2：订阅表（per-owner，替代 system_settings.keywords）───
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'keyword',
                polarity TEXT DEFAULT 'all',
                sensitivity TEXT DEFAULT 'balanced',
                frequency_min INTEGER DEFAULT 60,
                platforms TEXT DEFAULT '[]',
                push_mode TEXT DEFAULT 'important',
                show_risk_alert INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscription_owner ON subscription(owner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscription_active ON subscription(is_active)')

        # ── v2.2：订阅-话题多对多关联表 ─────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_topic (
                subscription_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                first_subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (subscription_id, topic_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_topic_sub ON subscription_topic(subscription_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_topic_topic ON subscription_topic(topic_id)')

        # ── v2.2：模型配置表（per-user，5 个 Agent 角色）────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                api_key TEXT,
                base_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_id, agent_role)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_config_owner ON model_config(owner_id)')

        # ── v2.2：配额表（per-user，含 v2.2 per-user 扫描配置）────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quota (
                owner_id TEXT PRIMARY KEY,
                max_subscriptions INTEGER DEFAULT 20,
                history_retention_days INTEGER DEFAULT 30,
                max_chat_per_month INTEGER DEFAULT 200,
                used_chat_this_month INTEGER DEFAULT 0,
                month_reset_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_interval_min REAL DEFAULT 60,
                scan_start_time TEXT DEFAULT '08:00',
                scan_paused INTEGER DEFAULT 0
            )
        ''')
        # ────────────────────────────────────────────────────────────

def _async_index_to_qdrant(result: dict):
    """异步将 ai_results 写入 Qdrant（不阻塞主流程）"""
    try:
        from .vector_store import index_ai_result
        index_ai_result(result)
        logger.info(f"[RAG Index] post_id={result['post_id']} 已写入 Qdrant")
    except Exception as e:
        logger.warning(f"[RAG Index] 索引失败（不影响主流程）：{e}")


def save_ai_result(post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time="未知时间", sentiment="Neutral", owner_id: Optional[str] = None):
    """
    WS4.6：owner_id 标识数据归属。
    - owner_id=None  → 公共/历史数据（所有用户可见）
    - owner_id="u_xxx" → 该用户私有数据
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ai_results
            (post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time, sentiment, owner_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post_id, platform, keyword, title, content, url, risk_level, core_issue, report, publish_time, sentiment, owner_id))
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
        "sentiment": sentiment,
    }
    threading.Thread(target=_async_index_to_qdrant, args=(result_dict,), daemon=True).start()
    # ───────────────────────────────────────────────

def get_latest_results(limit=50, owner_id: Optional[str] = None, is_admin: bool = False):
    """
    WS4.6：按 owner 过滤查询。
    - is_admin=True   → 看到全部（管理员）
    - owner_id 传值   → 仅看 owner_id == ? OR owner_id IS NULL（自己的 + 公共）
    - owner_id=None   → 仅看公共（owner_id IS NULL）
    """
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if is_admin:
            cursor.execute('SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?', (limit,))
        elif owner_id is not None:
            cursor.execute(
                'SELECT * FROM ai_results WHERE owner_id = ? OR owner_id IS NULL ORDER BY create_time DESC LIMIT ?',
                (owner_id, limit),
            )
        else:
            cursor.execute(
                'SELECT * FROM ai_results WHERE owner_id IS NULL ORDER BY create_time DESC LIMIT ?',
                (limit,),
            )
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
                        except (json.JSONDecodeError, TypeError, ValueError):
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
            "monitor_frequency": 1.0,
            "start_time": "08:00",
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
    alert_recommendation: str = "none",
    core_issue: str = "",
    report: str = "",
    platforms: list = None,
    sentiment: str = "neutral",
    owner_id: Optional[str] = None,
) -> bool:
    """
    创建或更新话题聚合记录。
    如果话题已存在（topic_id 相同），则合并（更新 post_count、scan_count、last_seen 等）。
    返回 True 表示新建，False 表示更新。

    WS4.6：owner_id 标识数据归属。
    - 新建时：写入 owner_id
    - 更新时：不动 owner_id（保持最初创建者；后续扫描若来自同 owner 自然一致）

    alert_recommendation: AI 最终决策结论，取值范围:
        - "high":     高风险预警（需处理）
        - "medium":   中风险（待观察）
        - "low":      低风险（忽略）
        - "none":     无风险（无需处理）
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
            # 更新：累加 post_count、scan_count，更新 last_seen（不动 owner_id）
            # WS6-C2 v2.2: WHERE 加 owner_id 过滤，避免跨租户覆盖
            cursor.execute('''
                UPDATE topic_summary SET
                    cluster_summary = COALESCE(NULLIF(?, ''), cluster_summary),
                    risk_level = MAX(risk_level, ?),
                    risk_class = CASE
                        WHEN ? > risk_level THEN ?
                        ELSE risk_class
                    END,
                    alert_recommendation = ?,
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
                WHERE topic_id = ? AND owner_id = ?
            ''', (
                cluster_summary, risk_level, risk_level, risk_class,
                alert_recommendation,
                core_issue, report,
                platforms_json,
                risk_level, sentiment,
                now, topic_id, topic_id, owner_id
            ))
            conn.commit()
            return False
        else:
            # 新建（带 owner_id）
            cursor.execute('''
                INSERT INTO topic_summary
                (topic_id, keyword, topic_name, cluster_summary, risk_level, risk_class,
                 alert_recommendation, core_issue, report, platforms, sentiment,
                 first_seen, last_seen, post_count, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                topic_id, keyword, topic_name, cluster_summary, risk_level, risk_class,
                alert_recommendation, core_issue, report, platforms_json, sentiment,
                now, now, 0, owner_id
            ))
            conn.commit()
            return True


def add_post_to_topic(topic_id: str, post_id: str, is_current: int = 1, owner_id: str = None):
    """将帖子关联到话题

    WS6-C2 v2.2: 必须传 owner_id，防止跨租户串改 ai_results.topic_id
    和 topic_summary.post_count。
    """
    if not owner_id:
        raise ValueError("add_post_to_topic 必须传 owner_id（WS6-C2 防越权）")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO topic_posts (topic_id, post_id, is_current)
            VALUES (?, ?, ?)
        ''', (topic_id, post_id, is_current))

        cursor.execute('''
            UPDATE ai_results SET topic_id = ?
            WHERE post_id = ? AND owner_id = ?
        ''', (topic_id, post_id, owner_id))

        cursor.execute('''
            UPDATE topic_summary SET post_count = (
                SELECT COUNT(*) FROM topic_posts WHERE topic_id = ?
            )
            WHERE topic_id = ? AND owner_id = ?
        ''', (topic_id, topic_id, owner_id))
        conn.commit()


def get_topic_summary_list(
    keyword: str = None,
    platform: str = None,
    sentiment: str = None,
    is_processed: int = None,
    limit: int = 50,
    owner_id: Optional[str] = None,
    is_admin: bool = False,
) -> list:
    """
    获取话题聚合列表（支持筛选）
    WS4.6：按 owner_id 过滤
    - is_admin=True → 全部
    - owner_id 传值 → owner_id = ? OR owner_id IS NULL
    - owner_id=None → 仅 owner_id IS NULL
    """
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

        # WS4.6 隔离
        if is_admin:
            pass  # 不过滤
        elif owner_id is not None:
            query += " AND (owner_id = ? OR owner_id IS NULL)"
            params.append(owner_id)
        else:
            query += " AND owner_id IS NULL"

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

        # alert_recommendation 字段（默认 none，兼容旧数据）
        d["alert_recommendation"] = d.get("alert_recommendation", "none")

        results.append(d)

    return results


def get_topic_summary_by_id(topic_id: str, owner_id: Optional[str] = None, is_admin: bool = False) -> dict:
    """
    获取单个话题聚合详情
    WS4.6：返回 None 表示无权访问 / 不存在
    """
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if is_admin:
            cursor.execute("SELECT * FROM topic_summary WHERE topic_id = ?", (topic_id,))
        elif owner_id is not None:
            cursor.execute(
                "SELECT * FROM topic_summary WHERE topic_id = ? AND (owner_id = ? OR owner_id IS NULL)",
                (topic_id, owner_id),
            )
        else:
            cursor.execute(
                "SELECT * FROM topic_summary WHERE topic_id = ? AND owner_id IS NULL",
                (topic_id,),
            )
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

    # alert_recommendation 字段（默认 none，兼容旧数据）
    d["alert_recommendation"] = d.get("alert_recommendation", "none")

    return d


def get_topic_posts(topic_id: str, owner_id: Optional[str] = None, is_admin: bool = False) -> list:
    """
    获取话题关联的所有帖子详情
    WS4.6：按 owner_id 过滤
    """
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if is_admin:
            cursor.execute('''
                SELECT ar.* FROM topic_posts tp
                JOIN ai_results ar ON ar.post_id = tp.post_id
                WHERE tp.topic_id = ?
                ORDER BY tp.is_current DESC, ar.create_time DESC
            ''', (topic_id,))
        elif owner_id is not None:
            cursor.execute('''
                SELECT ar.* FROM topic_posts tp
                JOIN ai_results ar ON ar.post_id = tp.post_id
                WHERE tp.topic_id = ? AND (ar.owner_id = ? OR ar.owner_id IS NULL)
                ORDER BY tp.is_current DESC, ar.create_time DESC
            ''', (topic_id, owner_id))
        else:
            cursor.execute('''
                SELECT ar.* FROM topic_posts tp
                JOIN ai_results ar ON ar.post_id = tp.post_id
                WHERE tp.topic_id = ? AND ar.owner_id IS NULL
                ORDER BY tp.is_current DESC, ar.create_time DESC
            ''', (topic_id,))
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def mark_topic_processed(topic_id: str, owner_id: str = None) -> bool:
    """标记话题为已处理

    WS6-C2 v2.2: 必须传 owner_id，防止跨租户标记。
    """
    if not owner_id:
        raise ValueError("mark_topic_processed 必须传 owner_id（WS6-C2 防越权）")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE topic_summary SET is_processed = 1 WHERE topic_id = ? AND owner_id = ?",
            (topic_id, owner_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# ============================================================
# 推送配置 CRUD
# ============================================================

def _ensure_push_settings_table():
    """确保 push_settings 表存在（v2.2：per-owner，含 rss 通道）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 检查表是否已有 owner_id 列（v2.2 迁移）
        cursor.execute("PRAGMA table_info(push_settings)")
        cols = {row[1] for row in cursor.fetchall()}

        if cols and "owner_id" not in cols:
            # 旧表（无 owner_id）→ 先备份到 push_settings_backup，再重建
            logger.warning("[push_settings] 旧表无 owner_id，备份后重建")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS push_settings_backup AS SELECT * FROM push_settings
            """)
            cursor.execute("DROP TABLE push_settings")
            cols = set()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_settings (
                owner_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                config_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (owner_id, channel)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_settings_owner ON push_settings(owner_id)')
        conn.commit()


def get_push_config(owner_id: str, channel: str) -> dict:
    """读取指定用户指定通道的配置（v2.2：per-owner）"""
    _ensure_push_settings_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT config_json FROM push_settings WHERE owner_id = ? AND channel = ?",
            (owner_id, channel)
        )
        row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    # 返回默认空配置
    defaults = {
        "email": {"enabled": False, "risk_min_level": 3},
        "wecom": {"enabled": False, "risk_min_level": 2},
        "feishu": {"enabled": False, "risk_min_level": 2},
        "rss": {"enabled": False, "access_token": ""},
    }
    return defaults.get(channel, {"enabled": False, "risk_min_level": 1})


def save_push_config(owner_id: str, channel: str, config: dict) -> None:
    """保存指定用户指定通道的配置（v2.2：per-owner）"""
    _ensure_push_settings_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO push_settings (owner_id, channel, config_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(owner_id, channel) DO UPDATE SET
                config_json = excluded.config_json,
                updated_at = CURRENT_TIMESTAMP
        ''', (owner_id, channel, json.dumps(config)))
        conn.commit()


def get_all_push_configs(owner_id: Optional[str] = None) -> dict[str, dict]:
    """返回某用户的所有推送通道配置（v2.2：per-owner）
    owner_id=None 时返回全部（admin 视角）"""
    _ensure_push_settings_table()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if owner_id is None:
            cursor.execute("SELECT owner_id, channel, config_json FROM push_settings")
            rows = cursor.fetchall()
        else:
            cursor.execute(
                "SELECT channel, config_json FROM push_settings WHERE owner_id = ?",
                (owner_id,)
            )
            rows = cursor.fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        if owner_id is None and len(row) == 3:
            # 全部模式：{(owner_id, channel): config}
            result[f"{row[0]}:{row[1]}"] = json.loads(row[2])
        else:
            result[row[0]] = json.loads(row[1])
    # 补全未配置的通道默认值
    default_channels = ("email", "wecom", "feishu", "rss")
    if owner_id is not None:
        for ch in default_channels:
            if ch not in result:
                if ch == "rss":
                    result[ch] = {"enabled": False, "access_token": ""}
                else:
                    result[ch] = {"enabled": False, "risk_min_level": 2}
    return result


# ============================================================
# v2.2 suppressed push tracking
# ============================================================

def record_suppressed_push(
    owner_id: str,
    keyword: str,
    topic_id: str,
    topic_name: str,
    reason: str = "agent_decision",
):
    """
    记录 Agent 压住的推送内容（push_mode=important 时 Agent 决定不推）。

    reason:
      - "agent_decision": Agent 判断为普通讨论，不值得推
      - "frequency_throttle": 同一话题短时间内多次更新，只推一次
    """
    insert_audit_log(
        action="suppressed_push",
        detail={
            "owner_id": owner_id,
            "topic_name": topic_name,
            "reason": reason,
        },
        keyword=keyword,
        topic_id=topic_id,
        level="INFO",
        owner_id=owner_id,  # v2.2: 写入专列，便于高效过滤
    )


def get_today_suppressed_count(owner_id: Optional[str] = None, is_admin: bool = False) -> int:
    """获取今日被 Agent 压住的推送数量（v2.2: 使用 owner_id 专列查询）。"""
    import datetime
    today = datetime.date.today().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if is_admin:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM audit_log "
                "WHERE action = 'suppressed_push' AND DATE(created_at) = ?",
                (today,),
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM audit_log "
                "WHERE action = 'suppressed_push' AND DATE(created_at) = ? "
                "AND owner_id = ?",
                (today, owner_id or ""),
            )
        row = cursor.fetchone()
    return row[0] if row else 0


# ============================================================
# 审计日志
# ============================================================

def insert_audit_log(
    action: str,
    detail: dict = None,
    keyword: str = "",
    topic_id: str = "",
    risk_level: int = 0,
    level: str = "INFO",
    owner_id: str = "",
) -> int:
    """插入一条审计日志，返回 rowid。

    v2.2: owner_id 单列存储（取代 detail.owner_id 的 json_extract 查询）。
    系统级事件可传空串。
    """
    init_radar_db()
    # 兼容旧调用方：若 detail 里塞了 owner_id 而未显式传，则提升到列
    if not owner_id and isinstance(detail, dict):
        owner_id = str(detail.get("owner_id") or "")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log
                (action, keyword, topic_id, risk_level, level, detail, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                keyword,
                topic_id,
                int(risk_level or 0),
                level,
                json.dumps(detail or {}, ensure_ascii=False),
                owner_id,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_audit_log(
    limit: int = 50,
    action: str = None,
    owner_id: Optional[str] = None,
) -> list:
    """查询审计日志（按时间倒序）。

    v2.2: owner_id 非 None 时仅返回该用户 + 系统级（owner_id 为空）的事件。
    owner_id=None 视为 admin/全局视角（返回全部）。
    """
    init_radar_db()
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        params: list = []
        where_clauses: list[str] = []
        if action:
            where_clauses.append("action = ?")
            params.append(action)
        if owner_id is not None:
            # per-user 视角：自己的 + 系统级（owner_id 为空）
            where_clauses.append("(owner_id = ? OR owner_id = '' OR owner_id IS NULL)")
            params.append(owner_id)
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(int(limit))
        cursor.execute(
            f"""
            SELECT id, action, keyword, topic_id, risk_level, level, detail, owner_id, created_at
            FROM audit_log
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        try:
            r["detail"] = json.loads(r.get("detail") or "{}")
        except Exception:
            r["detail"] = {}
    return rows


init_radar_db()