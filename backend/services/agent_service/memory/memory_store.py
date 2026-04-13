"""
AgentMemoryStore: Agent 记忆库 SQLite CRUD

幂等建表，查询时自动排除过期记录。
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from core.logger import get_logger

logger = get_logger("agent.memory")

AGENT_MEMORY_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "agent_memory.db"
)

class AgentMemoryStore:
    """Agent 记忆库 CRUD 操作"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or AGENT_MEMORY_DB_PATH
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表（幂等建表）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # entity_memory: 实体记忆表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    query_count INTEGER DEFAULT 1,
                    last_query_time TEXT NOT NULL,
                    last_summary TEXT,
                    sensitivity TEXT DEFAULT 'balanced',
                    created_at TEXT NOT NULL
                )
            """)
            # fact_memory: 事实记忆表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fact_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # pattern_memory: 行为模式表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
            """)
            # conversation_summary: 对话摘要表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    entities TEXT NOT NULL,
                    outcome TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        logger.info(f"[MemoryStore] 数据库初始化完成: {self.db_path}")

    # ==================== entity_memory ====================

    def upsert_entity(
        self,
        session_id: str,
        entity: str,
        entity_type: str,
        summary: str = None,
        sensitivity: str = "balanced"
    ) -> int:
        """写入或更新实体记忆（query_count++）"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 查是否存在
            cursor.execute(
                "SELECT id, query_count FROM entity_memory WHERE session_id=? AND entity=?",
                (session_id, entity)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE entity_memory
                    SET query_count = query_count + 1,
                        last_query_time = ?,
                        last_summary = COALESCE(?, last_summary),
                        sensitivity = COALESCE(?, sensitivity)
                    WHERE id = ?
                """, (now, summary, sensitivity, row[0]))
            else:
                cursor.execute("""
                    INSERT INTO entity_memory
                    (session_id, entity, entity_type, query_count, last_query_time, last_summary, sensitivity, created_at)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """, (session_id, entity, entity_type, now, summary, sensitivity, now))
            conn.commit()
            return cursor.lastrowid or 0

    def get_frequent_entities(self, session_id: str, min_count: int = 2) -> List[Dict]:
        """获取高频实体（query_count >= min_count）"""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT entity, entity_type, query_count, last_summary, sensitivity
                FROM entity_memory
                WHERE session_id=? AND query_count>=?
                ORDER BY query_count DESC
            """, (session_id, min_count))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== fact_memory ====================

    def insert_fact(
        self,
        session_id: str,
        entity: str,
        fact_type: str,
        content: str,
        confidence: float = 0.8,
        ttl_days: int = 90
    ) -> int:
        """写入事实记忆（含过期时间）"""
        now = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(days=ttl_days)).isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fact_memory
                (session_id, entity, fact_type, content, confidence, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, entity, fact_type, content, confidence, expires_at, now))
            conn.commit()
            return cursor.lastrowid

    def get_valid_facts(self, session_id: str) -> List[Dict]:
        """获取未过期的记忆（查询时自动排除）"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT entity, fact_type, content, confidence
                FROM fact_memory
                WHERE session_id=? AND expires_at > ?
                ORDER BY confidence DESC
            """, (session_id, now))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== pattern_memory ====================

    def upsert_pattern(self, session_id: str, pattern_type: str, pattern_value: str):
        """写入或更新行为模式"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pattern_memory SET
                    pattern_value=?,
                    frequency=frequency+1,
                    updated_at=?
                WHERE session_id=? AND pattern_type=?
            """, (pattern_value, now, session_id, pattern_type))
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO pattern_memory (session_id, pattern_type, pattern_value, frequency, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                """, (session_id, pattern_type, pattern_value, now))
            conn.commit()

    def get_recent_patterns(self, session_id: str, days: int = 7) -> List[Dict]:
        """获取最近 N 天内的行为模式"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pattern_type, pattern_value, frequency
                FROM pattern_memory
                WHERE session_id=? AND updated_at > ?
            """, (session_id, cutoff))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== conversation_summary ====================

    def save_summary(self, session_id: str, summary: str, entities: List[str], outcome: str = None):
        """保存对话摘要"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO conversation_summary (session_id, summary, entities, outcome, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, summary, json.dumps(entities, ensure_ascii=False), outcome, now))
            conn.commit()

    def get_summary(self, session_id: str) -> Optional[Dict]:
        """获取对话摘要"""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM conversation_summary WHERE session_id=?",
                (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== 清理 ====================

    def delete_session(self, session_id: str):
        """删除某次对话的所有记忆"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for table in ["entity_memory", "fact_memory", "pattern_memory", "conversation_summary"]:
                cursor.execute(f"DELETE FROM {table} WHERE session_id=?", (session_id,))
            conn.commit()

    def get_memory_stats(self) -> Dict[str, int]:
        """获取各表记录数"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            stats = {}
            for table in ["entity_memory", "fact_memory", "pattern_memory", "conversation_summary"]:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            return stats