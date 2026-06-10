# scripts/reset_db.py
"""
v2.2：清空业务数据脚本

按 v2.2 决策"重零开始"：
  - 清空所有业务表（ai_results / topic_summary / topic_posts / processed_posts
    / system_settings / push_settings / audit_log / subscription
    / subscription_topic / model_config / quota）
  - 保留 users / user_settings / token_blacklist（用户账号不丢）

⚠️ 运行前会要求二次确认。
用法：python scripts/reset_db.py [--force]
"""
import os
import sys
import argparse

# 让脚本能从 backend 目录运行
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# 业务表（清空）
BUSINESS_TABLES = [
    "ai_results",
    "topic_summary",
    "topic_posts",
    "processed_posts",
    "system_settings",
    "push_settings",
    "audit_log",
    "subscription",
    "subscription_topic",
    "model_config",
    "quota",
    "agent_memory",  # Agent 记忆表
]

# 保留表（不删）
KEEP_TABLES = {
    "users",
    "user_settings",
    "token_blacklist",
}


def confirm(prompt: str) -> bool:
    """要求用户输入 yes 才继续"""
    try:
        ans = input(f"{prompt} [yes/no]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("yes", "y")


def reset_database(force: bool = False):
    from core.database import get_db_connection
    from core.config import settings
    from core.logger import get_logger
    from core.auth_db import init_auth_tables
    from services.radar_service.db_manager import init_radar_db

    logger = get_logger("scripts.reset_db")
    db_path = settings.STATE_DB_PATH

    print(f"\n[reset_db] 目标数据库: {db_path}")

    if not os.path.exists(db_path):
        print(f"[reset_db] 数据库文件不存在，将新建")
    else:
        # 看看哪些表存在
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            existing = {row[0] for row in cursor.fetchall()}

        to_drop = [t for t in BUSINESS_TABLES if t in existing]
        keep = [t for t in KEEP_TABLES if t in existing]
        other = sorted(existing - set(BUSINESS_TABLES) - KEEP_TABLES)

        print(f"\n[reset_db] 准备 DROP 的业务表 ({len(to_drop)}):")
        for t in to_drop:
            print(f"  - {t}")
        if keep:
            print(f"\n[reset_db] 保留的表 ({len(keep)}):")
            for t in keep:
                print(f"  ✓ {t}")
        if other:
            print(f"\n[reset_db] ⚠️  其他未分类的表（不动）:")
            for t in other:
                print(f"  ? {t}")

    if not force:
        print("\n⚠️  此操作不可逆！")
        if not confirm("确认清空业务数据？"):
            print("[reset_db] 取消")
            return
    else:
        print("[reset_db] --force 模式，跳过确认")

    # DROP + 重建
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for t in BUSINESS_TABLES:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {t}")
                logger.info(f"[reset_db] DROP {t}")
            except Exception as e:
                logger.warning(f"[reset_db] DROP {t} 失败: {e}")
        conn.commit()
    print(f"[reset_db] 业务表已清空（{len(BUSINESS_TABLES)} 张）")

    # 重建 schema
    print("[reset_db] 重建 schema...")
    init_radar_db()  # 重建 radar 业务表 + 新增 v2.2 订阅/模型/配额表
    init_auth_tables()  # 重建 auth 侧（幂等）
    print("[reset_db] ✅ 完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清空 MediaRadar 业务数据（保留用户）")
    parser.add_argument("--force", action="store_true", help="跳过确认")
    args = parser.parse_args()
    reset_database(force=args.force)
