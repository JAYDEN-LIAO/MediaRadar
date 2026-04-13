"""
agent_memory_db.py - Agent 记忆库初始化

启动时自动创建 agent_memory.db 及各表（如已存在则跳过）。
"""
import os
import sqlite3

AGENT_MEMORY_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "agent_memory.db"
)

# 确保 data 目录存在
os.makedirs(os.path.dirname(AGENT_MEMORY_DB_PATH), exist_ok=True)

def init_db():
    """幂等建表：IF NOT EXISTS"""
    conn = sqlite3.connect(AGENT_MEMORY_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entity_memory (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            entity          TEXT NOT NULL,
            entity_type     TEXT NOT NULL,
            query_count     INTEGER DEFAULT 1,
            last_query_time TEXT NOT NULL,
            last_summary    TEXT,
            sensitivity     TEXT DEFAULT 'balanced',
            created_at      TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_memory (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            entity          TEXT NOT NULL,
            fact_type       TEXT NOT NULL,
            content         TEXT NOT NULL,
            confidence      REAL DEFAULT 0.8,
            expires_at      TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pattern_memory (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            pattern_type    TEXT NOT NULL,
            pattern_value   TEXT NOT NULL,
            frequency       INTEGER DEFAULT 1,
            updated_at      TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_summary (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT UNIQUE NOT NULL,
            summary         TEXT NOT NULL,
            entities        TEXT,
            outcome         TEXT,
            created_at      TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Agent 记忆库初始化完成: {AGENT_MEMORY_DB_PATH}")

# 启动时自动初始化
init_db()