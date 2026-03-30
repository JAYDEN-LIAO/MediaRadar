#!/usr/bin/env python3
"""
话题演化数据批量迁移脚本

将 SQLite ai_results 表中的历史舆情，按 keyword 聚合后，
批量生成 cluster_summary 并写入 Qdrant topic_evolution 集合。

用于初始化时一次性执行，或数据修复。

用法：
    python scripts/rag/migrate_topic_evolution.py                    # 迁移全部
    python scripts/rag/migrate_topic_evolution.py --limit 1000       # 最多迁移 1000 条 ai_results
    python scripts/rag/migrate_topic_evolution.py --dry-run          # 仅预览，不写入
"""

import sys
import os
import argparse

# 将 backend 目录加入 path
backend_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_dir))


def main():
    parser = argparse.ArgumentParser(
        description="将历史舆情聚合后迁移到 Qdrant topic_evolution 话题演化库"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="最多读取多少条 ai_results 进行聚合（默认 1000）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览要迁移的话题数量，不实际写入 Qdrant"
    )
    args = parser.parse_args()

    print(f"[TopicEvolution Migration] 开始迁移（limit={args.limit}, dry_run={args.dry_run}）")

    from services.radar_service.topic_tracker import (
        migrate_topics_from_ai_results,
        ensure_topic_collection_exists,
    )
    from services.radar_service.vector_store import get_topic_collection_info

    if args.dry_run:
        print("[TopicEvolution Migration] Dry-Run 模式，仅统计不写入")
        import sqlite3
        from core.database import get_db_connection

        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT keyword, COUNT(*) as cnt FROM ai_results GROUP BY keyword ORDER BY cnt DESC LIMIT ?",
                (args.limit,),
            )
            rows = cursor.fetchall()

        print(f"\n待迁移话题数：{len(rows)}")
        print("\n按关键词分布：")
        for r in rows:
            print(f"  {r['keyword']}: {r['cnt']} 条帖子")
        print("\n（Dry-Run 模式，未实际写入 Qdrant）")
        return

    # 确保集合存在
    print("[TopicEvolution Migration] 检查 topic_evolution 集合...")
    ensure_topic_collection_exists()
    print("[TopicEvolution Migration] 集合就绪")

    # 执行迁移
    migrated, total = migrate_topics_from_ai_results(limit=args.limit)
    print(f"[TopicEvolution Migration] 完成！共处理 {total} 个话题簇，写入成功 {migrated} 个")

    # 打印集合状态
    try:
        info = get_topic_collection_info()
        vectors_count = getattr(info, "vectors_count", None) or getattr(info, "points_count", "?")
        print(f"[TopicEvolution Migration] topic_evolution 集合向量数：{vectors_count}")
    except Exception as e:
        print(f"[TopicEvolution Migration] 获取集合状态失败（不影响迁移结果）: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[TopicEvolution Migration] 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
