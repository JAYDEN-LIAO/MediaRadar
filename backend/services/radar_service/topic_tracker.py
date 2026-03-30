# backend/services/radar_service/topic_tracker.py
"""
话题演化追踪器

职责：
1. 管理 topic_evolution 集合（HNSW 索引，cosine 相似度）
2. 接收 Cluster + 分析结果，构造/更新话题记录
3. 检索相似历史话题，构造演化时间线
4. 为 Analyst 提供 RAG 增强上下文

与 vector_store.py 的关系：
- vector_store.py：已有的 ai_results 级别单帖 RAG
- topic_tracker.py：新增的 topic_cluster 级别话题 RAG
- 两者互补，不冲突
"""

import sys
import os
import hashlib
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.config import settings
from core.logger import logger


TOPIC_COLLECTION_NAME = settings.TOPIC_COLLECTION
EMBEDDING_DIM = 1024  # BGE-M3 输出维度

# ===========================
# 1. 话题 ID 生成
# ===========================

def build_topic_id(keyword: str, topic_name: str) -> str:
    """
    话题唯一标识：keyword::topic_name 的 MD5。

    注意：topic_name 由 HDBSCAN + LLM 动态生成，
    不同扫描可能产生微小差异的名称，因此 topic_id
    仅用于同话题去重更新，不用于检索匹配（检索靠向量相似度）。
    """
    return hashlib.md5(f"{keyword}::{topic_name}".encode()).hexdigest()


# ===========================
# 2. 集合管理（代理到 vector_store）
# ===========================

def ensure_topic_collection_exists():
    """
    幂等创建 topic_evolution 集合。
    代理到 vector_store.py 的同名函数（复用同一 Qdrant 实例）。
    """
    from .vector_store import ensure_topic_collection_exists as _ensure
    _ensure()


# ===========================
# 3. Embedding 生成（话题文本）
# ===========================

def _embed_texts_for_topic(texts: list[str]) -> list[list[float]]:
    """
    调用 BGE-M3 对文本列表生成向量（话题检索用）。
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_BASE_URL,
    )

    resp = client.embeddings.create(
        input=texts,
        model=settings.EMBEDDING_MODEL or "BAAI/bge-m3",
    )
    return [item.embedding for item in resp.data]


# ===========================
# 4. LLM 生成簇摘要
# ===========================

def _call_topic_summary_llm(keyword: str, posts_text: str, n: int) -> str:
    """
    调用 DeepSeek 生成簇摘要。

    Args:
        keyword: 监控关键词
        posts_text: 多帖拼接的文本内容
        n: 帖子数量

    Returns:
        100-150 字的话题摘要
    """
    from openai import OpenAI

    prompt = f"""你是一个舆情话题归纳助手。

根据以下关于【{keyword}】的 {n} 条帖子，生成一段 100-150 字的话题摘要。
要求：
1. 概括核心事件/话题
2. 描述用户整体情绪倾向
3. 列出涉及的主要平台
4. 不要罗列具体帖子内容，要提炼共性

帖子列表：
{posts_text}

话题摘要："""

    client = OpenAI(
        api_key=settings.ANALYST_API_KEY,
        base_url=settings.ANALYST_BASE_URL,
    )

    try:
        response = client.chat.completions.create(
            model=settings.ANALYST_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的舆情分析助手，请生成简洁凝练的话题摘要。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300,
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        logger.error(f"[TopicTracker] 簇摘要生成失败: {e}")
        return ""


def generate_cluster_summary(cluster_posts: list[dict], keyword: str) -> str:
    """
    对 Cluster 内的多个帖子生成一句话摘要。

    Args:
        cluster_posts: Cluster.posts (list[dict])
        keyword: 监控关键词

    Returns:
        100-150 字的话题摘要
    """
    if not cluster_posts:
        return ""

    # 拼接多帖内容（限制总长度避免 token 溢出）
    posts_text_parts = []
    total_chars = 0
    max_chars = 1500

    for p in cluster_posts:
        part = f"标题：{p.get('title', '')}\n内容：{(p.get('content') or '')[:200]}\n"
        if total_chars + len(part) > max_chars:
            break
        posts_text_parts.append(part)
        total_chars += len(part)

    posts_text = "\n---\n".join(posts_text_parts)
    n = len(posts_text_parts)

    return _call_topic_summary_llm(keyword, posts_text, n)


# ===========================
# 5. 检索相似历史话题
# ===========================

def retrieve_similar_topics(
    keyword: str,
    topic_name: str,
    cluster_summary: str,
    top_k: int = 5,
    score_threshold: float = 0.75,
) -> list[dict]:
    """
    检索与当前话题最相似的历史话题簇。

    步骤：
    1. 拼接 query_text = f"话题：{topic_name}\\n内容：{cluster_summary}"
    2. BGE-M3 embedding 生成向量
    3. Qdrant 检索，keyword 精确过滤，score_threshold 过滤
    4. 按 score 降序返回

    Returns:
        [
            {
                "topic_id": str,
                "topic_name": str,
                "keyword": str,
                "cluster_summary": str,
                "risk_level": int,
                "first_seen": str,
                "last_seen": str,
                "post_count": int,
                "platforms": list[str],
                "core_issue": str,
                "scan_count": int,
                "score": float,
            }
        ]
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # 1. 生成查询向量
        query_text = f"话题：{topic_name}\n内容摘要：{cluster_summary}"
        vectors = _embed_texts_for_topic([query_text])
        query_vector = vectors[0]

        # 2. Qdrant 检索
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )

        results = client.query_points(
            collection_name=TOPIC_COLLECTION_NAME,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="keyword",
                        match=MatchValue(value=keyword),
                    )
                ]
            ),
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        # 3. 格式化返回
        formatted = []
        points = getattr(results, 'points', []) or []
        for hit in points:
            p = hit.payload or {}
            formatted.append({
                "topic_id": p.get("topic_id", ""),
                "topic_name": p.get("topic_name", ""),
                "keyword": p.get("keyword", ""),
                "cluster_summary": p.get("cluster_summary", ""),
                "risk_level": int(p.get("risk_level", 0)),
                "first_seen": p.get("first_seen", ""),
                "last_seen": p.get("last_seen", ""),
                "post_count": int(p.get("post_count", 0)),
                "platforms": p.get("platforms", []),
                "core_issue": p.get("core_issue", ""),
                "scan_count": int(p.get("scan_count", 0)),
                "score": hit.score,
            })

        logger.info(
            f"[TopicTracker] 检索 keyword={keyword}, topic={topic_name[:20]}..., "
            f"返回 {len(formatted)} 条（阈值={score_threshold}）"
        )
        return formatted

    except Exception as e:
        logger.warning(f"[TopicTracker] 检索相似历史话题失败: {e}")
        return []


# ===========================
# 6. 构造话题演化时间线
# ===========================

def build_evolution_timeline(
    current_topic: dict,
    similar_topics: list[dict],
) -> dict:
    """
    将当前话题与历史相似话题合并，构造完整演化时间线。

    Args:
        current_topic: {
            "topic_name": str,
            "keyword": str,
            "cluster_summary": str,
            "risk_level": int | None,  # 分析前为 None
        }
        similar_topics: retrieve_similar_topics() 的返回结果

    Returns:
        演化时间线字典，结构如下：
        {
            "is_new_topic": bool,
            "topic_id": str,
            "total_scan_count": int,
            "total_post_count": int,
            "duration_days": int,
            "risk_evolution_path": str,   # 如 "2 → 3 → 4"
            "current_risk_level": int,
            "evolution_signal": str,        # "escalating" / "stable" / "deescalating"
            "timeline": [
                {
                    "scan_time": str,
                    "risk_level": int,
                    "core_issue": str,
                    "summary": str,
                    "post_count": int,
                    "platforms": list[str],
                    "is_current": bool,
                }
            ],
        }
    """
    now = datetime.datetime.now()

    if not similar_topics:
        # 新话题首次出现
        topic_id = build_topic_id(
            current_topic.get("keyword", ""),
            current_topic.get("topic_name", "")
        )
        return {
            "is_new_topic": True,
            "topic_id": topic_id,
            "total_scan_count": 0,
            "total_post_count": 0,
            "duration_days": 0,
            "risk_evolution_path": "",
            "current_risk_level": current_topic.get("risk_level") or 0,
            "evolution_signal": "unknown",
            "timeline": [],
        }

    # 构造时间线：历史话题 + 当前
    timeline = []

    for st in similar_topics:
        first_seen_str = st.get("first_seen", "")
        last_seen_str = st.get("last_seen", "")

        # 计算话题持续天数（从 first_seen 到 last_seen）
        duration_days = 0
        if first_seen_str and last_seen_str:
            try:
                first_dt = datetime.datetime.fromisoformat(first_seen_str.replace("Z", "+00:00"))
                last_dt = datetime.datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                # 转为本地时间（ naive ）
                now_naive = now.replace(tzinfo=None)
                first_naive = first_dt.replace(tzinfo=None)
                last_naive = last_dt.replace(tzinfo=None)
                duration_days = (last_naive - first_naive).days
            except Exception:
                duration_days = 0

        timeline.append({
            "scan_time": last_seen_str or first_seen_str or "未知",
            "risk_level": st.get("risk_level", 0),
            "core_issue": st.get("core_issue", ""),
            "summary": st.get("cluster_summary", ""),
            "post_count": st.get("post_count", 0),
            "platforms": st.get("platforms", []),
            "is_current": False,
        })

    # 按时间升序排序（从早到晚）
    timeline.sort(key=lambda x: x["scan_time"] or "")

    # 风险演变路径
    risk_levels = [item["risk_level"] for item in timeline]
    current_risk = current_topic.get("risk_level") or (risk_levels[-1] if risk_levels else 0)
    if current_risk:
        risk_levels.append(current_risk)

    if len(risk_levels) >= 2:
        path_parts = [str(r) for r in risk_levels]
        risk_evolution_path = " → ".join(path_parts)
    else:
        risk_evolution_path = str(current_risk) if current_risk else ""

    # 演化信号判断
    if len(risk_levels) >= 2:
        earliest = risk_levels[0]
        latest = risk_levels[-1]
        diff = latest - earliest
        if diff >= 2:
            evolution_signal = "escalating"
        elif diff <= -2:
            evolution_signal = "deescalating"
        else:
            evolution_signal = "stable"
    else:
        evolution_signal = "unknown"

    # 统计
    topic_id = build_topic_id(
        current_topic.get("keyword", ""),
        current_topic.get("topic_name", "")
    )
    total_scan_count = sum(st.get("scan_count", 0) for st in similar_topics)
    total_post_count = sum(st.get("post_count", 0) for st in similar_topics)

    # 计算话题持续天数（最早出现到现在）
    duration_days = 0
    if timeline:
        first_time_str = timeline[0].get("scan_time", "")
        if first_time_str:
            try:
                first_dt = datetime.datetime.fromisoformat(first_time_str.replace("Z", "+00:00"))
                now_naive = now.replace(tzinfo=None)
                first_naive = first_dt.replace(tzinfo=None)
                duration_days = (now_naive - first_naive).days
            except Exception:
                duration_days = 0

    return {
        "is_new_topic": False,
        "topic_id": topic_id,
        "total_scan_count": total_scan_count,
        "total_post_count": total_post_count,
        "duration_days": duration_days,
        "risk_evolution_path": risk_evolution_path,
        "current_risk_level": current_risk,
        "evolution_signal": evolution_signal,
        "timeline": timeline,
    }


# ===========================
# 7. 写入 / 更新话题记录
# ===========================

def _upsert_topic_point(point: dict) -> bool:
    """
    将单个话题 point 写入 Qdrant。
    内部使用 upsert（存在则更新，不存在则插入）。
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct

        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )

        pt = PointStruct(
            id=point["topic_id"],
            vector=point["vector"],
            payload=point["payload"],
        )

        operation_info = client.upsert(
            collection_name=TOPIC_COLLECTION_NAME,
            points=[pt],
            wait=True,
        )
        return getattr(operation_info, "status", None) == "completed"

    except Exception as e:
        logger.error(f"[TopicTracker] 写入话题失败: {e}")
        return False


def index_or_update_topic(
    topic_id: str,
    keyword: str,
    topic_name: str,
    cluster_summary: str,
    risk_level: int,
    posts: list[dict],
    core_issue: str,
    report: str,
) -> bool:
    """
    写入新话题 OR 更新已有话题。

    逻辑：
    1. 检查 topic_id 是否已存在
    2. 存在 → 更新 last_seen、scan_count+=1、post_count+=len(posts)
    3. 不存在 → 写入新记录（first_seen = last_seen = now）

    仅处理 risk_level >= 3 的高危舆情。

    Returns: True 成功，False 失败
    """
    try:
        from qdrant_client import QdrantClient

        ensure_topic_collection_exists()

        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )

        # 尝试获取已有记录
        try:
            existing = client.retrieve(
                collection_name=TOPIC_COLLECTION_NAME,
                ids=[topic_id],
            )
            exists = bool(existing and len(existing) > 0)
        except Exception:
            exists = False

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构造向量检索用文本（用于 embedding）
        text_to_embed = (
            f"话题：{topic_name}\n"
            f"内容摘要：{cluster_summary[:200]}\n"
            f"风险等级：{risk_level}\n"
            f"核心问题：{core_issue}"
        )
        vectors = _embed_texts_for_topic([text_to_embed])
        vector = vectors[0]

        # 提取涉及平台
        platforms = list(set(p.get("platform", "") or "" for p in posts if p.get("platform")))

        if exists:
            # 更新已有记录：累加 scan_count 和 post_count，更新 last_seen
            existing_payload = existing[0].payload
            new_scan_count = int(existing_payload.get("scan_count", 0)) + 1
            new_post_count = int(existing_payload.get("post_count", 0)) + len(posts)

            # 保留最早出现的 first_seen
            first_seen = existing_payload.get("first_seen", now_str)
            # 如果核心问题变了（风险升级），追加说明
            if existing_payload.get("core_issue", "") != core_issue:
                core_issue = existing_payload.get("core_issue", "") + " → " + core_issue

            payload = {
                "topic_id": topic_id,
                "keyword": keyword,
                "topic_name": topic_name,
                "cluster_summary": cluster_summary,
                "risk_level": risk_level,
                "first_seen": first_seen,
                "last_seen": now_str,
                "post_count": new_post_count,
                "platforms": list(set(existing_payload.get("platforms", []) + platforms)),
                "core_issue": core_issue[:200] if core_issue else "",
                "report": report[:500] if report else "",
                "scan_count": new_scan_count,
            }
            logger.info(
                f"[TopicTracker] 更新话题 topic_id={topic_id}, "
                f"scan_count={new_scan_count}, post_count={new_post_count}"
            )
        else:
            # 新建记录
            payload = {
                "topic_id": topic_id,
                "keyword": keyword,
                "topic_name": topic_name,
                "cluster_summary": cluster_summary,
                "risk_level": risk_level,
                "first_seen": now_str,
                "last_seen": now_str,
                "post_count": len(posts),
                "platforms": platforms,
                "core_issue": core_issue[:200] if core_issue else "",
                "report": report[:500] if report else "",
                "scan_count": 1,
            }
            logger.info(f"[TopicTracker] 新建话题 topic_id={topic_id}, keyword={keyword}")

        point = {
            "topic_id": topic_id,
            "vector": vector,
            "payload": payload,
        }
        return _upsert_topic_point(point)

    except Exception as e:
        logger.error(f"[TopicTracker] index_or_update_topic 失败: {e}")
        return False


# ===========================
# 8. 获取话题历史（用于详情页）
# ===========================

def get_topic_history(topic_id: str, keyword: str) -> dict:
    """
    根据 topic_id + keyword 查询完整话题历史。

    用于前端 detail.vue 展示"话题追踪"卡片。

    检索策略：
    1. 先用 topic_id 精确匹配（已有记录）
    2. 如果精确匹配失败，用 keyword + 相似检索兜底
    3. 如果都无结果，返回 is_new_topic=True

    Returns:
        {
            "is_new_topic": bool,
            "topic_id": str,
            "topic_name": str,
            "keyword": str,
            "evolution": {...},  # build_evolution_timeline 的输出
        }
    """
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10,
        )

        # 1. 精确查询（优先用 topic_id）
        if topic_id:
            try:
                results = client.retrieve(
                    collection_name=TOPIC_COLLECTION_NAME,
                    ids=[topic_id],
                )
                if results and len(results) > 0:
                    p = results[0].payload
                    similar_topics = [{
                        "topic_id": p.get("topic_id", ""),
                        "topic_name": p.get("topic_name", ""),
                        "keyword": p.get("keyword", ""),
                        "cluster_summary": p.get("cluster_summary", ""),
                        "risk_level": int(p.get("risk_level", 0)),
                        "first_seen": p.get("first_seen", ""),
                        "last_seen": p.get("last_seen", ""),
                        "post_count": int(p.get("post_count", 0)),
                        "platforms": p.get("platforms", []),
                        "core_issue": p.get("core_issue", ""),
                        "scan_count": int(p.get("scan_count", 0)),
                        "score": 1.0,
                    }]
                    current_topic = {
                        "topic_name": p.get("topic_name", ""),
                        "keyword": keyword,
                        "cluster_summary": p.get("cluster_summary", ""),
                        "risk_level": int(p.get("risk_level", 0)),
                    }
                    evolution = build_evolution_timeline(current_topic, similar_topics)
                    return {
                        "is_new_topic": False,
                        "topic_id": topic_id,
                        "topic_name": p.get("topic_name", ""),
                        "keyword": keyword,
                        "evolution": evolution,
                    }
            except Exception:
                pass

        # 2. 兜底：keyword 模糊检索最近 5 条
        try:
            dummy_vector = _embed_texts_for_topic([keyword])[0]
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            results = client.query_points(
                collection_name=TOPIC_COLLECTION_NAME,
                query=dummy_vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="keyword",
                            match=MatchValue(value=keyword),
                        )
                    ]
                ),
                limit=5,
                score_threshold=0.0,  # 不过滤低分，只做兜底
                with_payload=True,
            )
            points = getattr(results, 'points', []) or []
            if points:
                p = points[0].payload
                similar_topics = [{
                    "topic_id": p.get("topic_id", ""),
                    "topic_name": p.get("topic_name", ""),
                    "keyword": p.get("keyword", ""),
                    "cluster_summary": p.get("cluster_summary", ""),
                    "risk_level": int(p.get("risk_level", 0)),
                    "first_seen": p.get("first_seen", ""),
                    "last_seen": p.get("last_seen", ""),
                    "post_count": int(p.get("post_count", 0)),
                    "platforms": p.get("platforms", []),
                    "core_issue": p.get("core_issue", ""),
                    "scan_count": int(p.get("scan_count", 0)),
                    "score": 1.0,
                }]
                current_topic = {
                    "topic_name": p.get("topic_name", ""),
                    "keyword": keyword,
                    "cluster_summary": "",
                    "risk_level": int(p.get("risk_level", 0)),
                }
                evolution = build_evolution_timeline(current_topic, similar_topics)
                return {
                    "is_new_topic": False,
                    "topic_id": p.get("topic_id", ""),
                    "topic_name": p.get("topic_name", ""),
                    "keyword": keyword,
                    "evolution": evolution,
                }
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"[TopicTracker] get_topic_history 失败: {e}")

    # 3. 确实无记录
    return {
        "is_new_topic": True,
        "topic_id": topic_id or "",
        "topic_name": "",
        "keyword": keyword,
        "evolution": {
            "is_new_topic": True,
            "topic_id": topic_id or "",
            "total_scan_count": 0,
            "total_post_count": 0,
            "duration_days": 0,
            "risk_evolution_path": "",
            "current_risk_level": 0,
            "evolution_signal": "unknown",
            "timeline": [],
        },
    }


# ===========================
# 9. 历史数据迁移（从 ai_results 到话题演化库）
# ===========================

def migrate_topics_from_ai_results(limit: int = 1000) -> tuple[int, int]:
    """
    从 ai_results 表读取历史舆情，按 keyword 聚合后，
    批量生成 cluster_summary 并写入 topic_evolution 集合。

    用于初始化时一次性执行，或数据修复。

    Args:
        limit: 最多迁移多少条 ai_results（默认 1000）

    Returns:
        (成功写入话题数, 总处理话题数)
    """
    import sqlite3
    from collections import defaultdict

    ensure_topic_collection_exists()

    # 1. 读取 ai_results
    from core.database import get_db_connection

    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()

    results = [dict(r) for r in rows]
    total = len(results)
    logger.info(f"[TopicTracker Migration] 共读取 {total} 条 ai_results")

    if total == 0:
        return 0, 0

    # 2. 按 keyword 分组
    by_keyword = defaultdict(list)
    for r in results:
        by_keyword[r.get("keyword", "unknown")].append(r)

    # 3. 每个 keyword 生成一个话题簇摘要
    success_count = 0
    for keyword, posts in by_keyword.items():
        if not keyword:
            continue

        # 用前 N 条帖子生成摘要
        sample_posts = posts[:10]
        cluster_summary = generate_cluster_summary(sample_posts, keyword)

        # 统计风险等级（取最高，兼容字符串和整数）
        def _parse_risk(v):
            try:
                return int(v)
            except (ValueError, TypeError):
                # 兼容 'low'/'medium'/'high' 等历史字符串值
                mapping = {"low": 1, "medium": 2, "high": 3, "very_high": 4, "critical": 5}
                return mapping.get(str(v).lower(), 1)
        risk_level = max(_parse_risk(p.get("risk_level", 1)) for p in posts)

        # 收集平台
        platforms = list(set(p.get("platform", "") for p in posts if p.get("platform")))

        # 发布时间范围
        publish_times = [p.get("publish_time", "") for p in posts if p.get("publish_time")]
        first_seen = min(publish_times) if publish_times else ""
        last_seen = max(publish_times) if publish_times else ""

        # 核心问题（取风险最高的那个）
        top_post = max(posts, key=lambda x: _parse_risk(x.get("risk_level", 1)))
        core_issue = top_post.get("core_issue", "")
        report = top_post.get("report", "")

        # 生成 topic_name
        titles = [p.get("title", "") for p in sample_posts if p.get("title")]
        topic_name = titles[0][:30] if titles else keyword

        topic_id = build_topic_id(keyword, topic_name)

        ok = index_or_update_topic(
            topic_id=topic_id,
            keyword=keyword,
            topic_name=topic_name,
            cluster_summary=cluster_summary,
            risk_level=risk_level,
            posts=sample_posts,
            core_issue=core_issue,
            report=report,
        )
        if ok:
            success_count += 1

    logger.info(f"[TopicTracker Migration] 完成，成功写入 {success_count}/{len(by_keyword)} 个话题簇")
    return success_count, len(by_keyword)
