# yq_radar/db_manager.py
import sqlite3
import os
import json
# 状态数据库路径
STATE_DB_PATH = "radar_state.db"

def init_radar_db():
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    # 原有的：创建已处理帖子记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_posts (
            post_id TEXT PRIMARY KEY,
            platform TEXT,
            process_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 【修改】：创建 AI 分析结果表，增加 title, content, url 三个字段！
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
    # 【新增】：创建系统设置表（只存一行 JSON 数据）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            config_json TEXT
        )
    ''')
    
    # 💡 贴心设计：如果你之前已经有旧数据库了，这段代码会自动帮你加上新字段，免得报错
    try:
        cursor.execute("ALTER TABLE ai_results ADD COLUMN title TEXT")
        cursor.execute("ALTER TABLE ai_results ADD COLUMN content TEXT")
        cursor.execute("ALTER TABLE ai_results ADD COLUMN url TEXT")
    except sqlite3.OperationalError:
        pass # 如果字段已经存在，就静默跳过

    conn.commit()
    conn.close()

# 【修改】：接收并保存原始帖子的内容
def save_ai_result(post_id, platform, keyword, title, content, url, risk_level, core_issue, report):
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO ai_results 
        (post_id, platform, keyword, title, content, url, risk_level, core_issue, report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (post_id, platform, keyword, title, content, url, risk_level, core_issue, report))
    conn.commit()
    conn.close()

# 供 API 层拉取最新数据的方法
def get_latest_results(limit=50):
    conn = sqlite3.connect(STATE_DB_PATH)
    conn.row_factory = sqlite3.Row # 转换为字典格式
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# 保留单条检查接口（兼容旧代码，但在大数据量下不再推荐使用）
def is_processed(post_id):
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM processed_posts WHERE post_id = ?', (post_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# 保留单条标记接口
def mark_processed(post_id, platform):
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    try:
        # 使用 INSERT OR IGNORE 更加优雅，代替原来的 try-except 捕获主键冲突
        cursor.execute('INSERT OR IGNORE INTO processed_posts (post_id, platform) VALUES (?, ?)', (post_id, platform))
        conn.commit()
    finally:
        conn.close()

# ================= 新增：批量处理利器 =================

def get_processed_status_batch(post_ids):
    """【新增】批量检查一批帖子ID，返回其中已经被处理过的 ID 集合 (Set)"""
    if not post_ids:
        return set()
        
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    
    # 动态生成占位符，例如: (?, ?, ?)
    placeholders = ','.join(['?'] * len(post_ids))
    query = f"SELECT post_id FROM processed_posts WHERE post_id IN ({placeholders})"
    
    cursor.execute(query, tuple(post_ids))
    # 使用集合 (set) 存储，后续查询速度是 O(1)，极快
    processed_ids = {row[0] for row in cursor.fetchall()} 
    conn.close()
    
    return processed_ids

def mark_processed_batch(post_info_list):
    """
    【新增】批量将帖子标记为已处理
    :param post_info_list: 形如 [("id1", "wb"), ("id2", "xhs")] 的列表
    """
    if not post_info_list:
        return
        
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    try:
        # executemany 配合 INSERT OR IGNORE：一次性批量写入，遇到重复自动跳过
        cursor.executemany(
            'INSERT OR IGNORE INTO processed_posts (post_id, platform) VALUES (?, ?)', 
            post_info_list
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"⚠️ 批量写入数据库时发生错误: {e}")
    finally:
        conn.close()

# =====================================================

def get_unprocessed_posts(crawler_db_path, platform):
    """
    终极自适应读取：自动探测表结构，并在内存中完成批量过滤，速度提升数百倍
    """
    if not os.path.exists(crawler_db_path):
        print(f"⚠️ 找不到爬虫数据库文件: {crawler_db_path}")
        return []

    conn = sqlite3.connect(crawler_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    unprocessed_posts = []
    
    if platform == "wb":
        table_name = "weibo_note"
    elif platform == "xhs":
        table_name = "xhs_note"
    else:
        print(f"⚠️ 暂不支持的平台自动读取: {platform}")
        return []

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        
        if not columns_info:
            print(f"⚠️ 数据库中不存在表 {table_name}，可能该平台还未抓取到数据。")
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

        if not id_col or not content_col:
            print(f"⚠️ 无法在 {table_name} 中找到核心字段。")
            return []

        query_cols = [id_col, content_col]
        if url_col: query_cols.append(url_col)
        if title_col: query_cols.append(title_col)
        
        query_cols_str = ", ".join(query_cols)

        # 执行查询获取数据
        cursor.execute(f'''
            SELECT {query_cols_str} 
            FROM {table_name} 
            ORDER BY ROWID DESC LIMIT 200
        ''')
        rows = cursor.fetchall()
        
        # ----------------- 性能优化核心区 -----------------
        # 1. 提取本次查询到的所有帖子的 ID
        all_post_ids = [str(row[id_col]) for row in rows]
        
        # 2. 一次性查出其中哪些已经处理过了
        processed_ids_set = get_processed_status_batch(all_post_ids)
        
        # 3. 在内存中进行对比过滤，不再频繁开关数据库
        for row in rows:
            post_id = str(row[id_col])
            
            if post_id not in processed_ids_set:
                unprocessed_posts.append({
                    "post_id": post_id,
                    "title": row[title_col] if title_col else "无标题",
                    "content": row[content_col] or "无正文",
                    "url": row[url_col] if url_col else f"未知链接 ({post_id})",
                    "platform": platform
                })
        # --------------------------------------------------
                
    except sqlite3.OperationalError as e:
        print(f"⚠️ 数据库读取错误: {e}")
    finally:
        conn.close()
        
    return unprocessed_posts

# ================= 新增：系统设置读写 =================
def get_system_settings():
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT config_json FROM system_settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    else:
        # 默认出厂设置
        default_config = {
            "keywords": ["北京银行"],
            "platforms": ["wb", "xhs"],
            "push_summary": True,
            "push_time": "18:00",
            "alert_negative": True,
            "monitor_frequency": 1.0 # 单位：小时
        }
        save_system_settings(default_config)
        return default_config

def save_system_settings(config_dict):
    conn = sqlite3.connect(STATE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO system_settings (id, config_json)
        VALUES (1, ?)
    ''', (json.dumps(config_dict),))
    conn.commit()
    conn.close()

# 模块加载时自动初始化状态库
init_radar_db()