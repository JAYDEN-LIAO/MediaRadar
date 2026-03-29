#!/usr/bin/env python3
"""
历史舆情数据批量迁移脚本

将 SQLite ai_results 表中所有已有数据批量写入 Qdrant 向量库。
用于项目初始化时一次性执行，或数据修复。

用法：
    python scripts/rag/migrate_history_to_qdrant.py                    # 迁移全部
    python scripts/rag/migrate_history_to_qdrant.py --limit 10000      # 最多迁移 10000 条
    python scripts/rag/migrate_history_to_qdrant.py --batch-size 200   # 每批 200 条
"""

import sys
import os
import argparse
import sqlite3

# 将 backend 目录加入 path
backend_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_dir))

from core.database import get_db_connection
from core.logger import logger
from services.radar_service.vector_store import (
    ensure_collection_exists,
    batch_index_ai_results,
    get_collection_stats,
)
from services.radar_service import db_manager


def migrate(limit: int = None, batch_size: int = 100):
    """
    从 SQLite 读取所有 ai_results，批量写入 Qdrant

    Args:
        limit: 最多迁移条数（None = 全部）
        batch_size: 每批写入数量

    Returns:
        (成功写入数, 总数)
    """
    # 1. 确保集合存在
    print("[Migration] 检查 Qdrant 集合...")
    ensure_collection_exists()
    print("[Migration] Qdrant 集合就绪")

    # 2. 读取所有 ai_results
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if limit:
            cursor.execute(
                "SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?",
                (limit,)
            )
        else:
            cursor.execute("SELECT * FROM ai_results ORDER BY create_time DESC")
        rows = cursor.fetchall()

    results = [dict(r) for r in rows]
    total = len(results)

    if total == 0:
        print("[Migration] ai_results 表为空，无数据需要迁移")
        return 0, 0

    print(f"[Migration] 共找到 {total} 条历史舆情待迁移（batch_size={batch_size}）")

    # 3. 分批写入
    success_count = 0
    for i in range(0, total, batch_size):
        batch = results[i:i + batch_size]
        count = batch_index_ai_results(batch)
        success_count += count
        print(f"[Migration] 进度 {min(i + batch_size, total)}/{total}，成功写入 {success_count} 条")

    print(f"[Migration] 迁移完成！共写入 {success_count}/{total} 条")

    # 4. 打印 Qdrant 集合状态
    stats = get_collection_stats()
    if stats:
        print(f"[Migration] Qdrant 集合状态：vectors={stats.get('vectors_count', '?')}, points={stats.get('points_count', '?')}")

    return success_count, total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将历史舆情数据迁移到 Qdrant 向量库")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多迁移条数（默认全部）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批量写入大小（默认 100）"
    )
    args = parser.parse_args()

    try:
        migrate(limit=args.limit, batch_size=args.batch_size)
    except Exception as e:
        print(f"[Migration] 迁移失败: {e}")
        sys.exit(1)
