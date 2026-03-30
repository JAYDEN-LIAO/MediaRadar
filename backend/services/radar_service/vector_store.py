# backend/services/radar_service/vector_store.py
"""
Qdrant 向量库封装层

使用 qdrant-client SDK 管理集合和向量操作。

职责：
1. 集合管理（创建、检查、HNSW 索引配置）
2. 写入（单条 / 批量，SDK 自动处理 64 条上限分批）
3. 检索（按 keyword 过滤 + cosine 相似度 top_k）
4. 历史数据迁移

向量模型：BGE-M3（复用 embedding_client）
"""

import sys
import os
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.config import settings
from core.logger import logger


def _post_id_to_qdrant_id(post_id: str) -> str:
    """
    将原始 post_id 转换为 Qdrant 合法的 ID 格式。

    Qdrant numeric ID 上限为 uint64 (max ~9.2×10^18)，
    而数据库 post_id 通常是超过此范围的 16 位整数。
    因此统一转为 MD5 哈希的 32 位十六进制字符串。
    """
    return hashlib.md5(str(post_id).encode()).hexdigest()

# Qdrant 配置
QDRANT_HOST = settings.QDRANT_HOST
QDRANT_PORT = settings.QDRANT_PORT
COLLECTION_NAME = settings.QDRANT_COLLECTION
EMBEDDING_DIM = 1024  # BGE-M3 输出维度

# ===========================
# 1. Qdrant 客户端初始化（懒加载）
# ===========================

_client = None


def _get_client():
    """获取 Qdrant 客户端单例"""
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            timeout=10,
        )
    return _client


# ===========================
# 2. 集合管理
# ===========================

def collection_exists() -> bool:
    """检查集合是否存在"""
    try:
        client = _get_client()
        client.get_collection(collection_name=COLLECTION_NAME)
        return True
    except Exception:
        return False


def ensure_collection_exists():
    """
    幂等创建集合（集合存在时跳过，不存在则创建）
    """
    if collection_exists():
        logger.info(f"[Qdrant] 集合 '{COLLECTION_NAME}' 已存在，跳过创建")
        return

    from qdrant_client.models import Distance, VectorParams, HnswConfigDiff, OptimizersConfigDiff

    client = _get_client()
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10000,
        ),
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=10000,
        ),
    )
    logger.info(f"[Qdrant] 集合 '{COLLECTION_NAME}' 创建成功（dim={EMBEDDING_DIM}, HNSW m=16, ef=100）")


def get_collection_info():
    """获取集合详细信息"""
    client = _get_client()
    return client.get_collection(collection_name=COLLECTION_NAME)


def delete_collection():
    """删除集合（仅用于数据修复）"""
    client = _get_client()
    client.delete_collection(collection_name=COLLECTION_NAME)
    logger.info(f"[Qdrant] 集合 '{COLLECTION_NAME}' 已删除")


# ===========================
# 2b. 话题演化集合管理（topic_evolution）
# ===========================

TOPIC_COLLECTION_NAME = settings.TOPIC_COLLECTION


def topic_collection_exists() -> bool:
    """检查话题演化集合是否存在"""
    try:
        client = _get_client()
        client.get_collection(collection_name=TOPIC_COLLECTION_NAME)
        return True
    except Exception:
        return False


def ensure_topic_collection_exists():
    """
    幂等创建话题演化集合（集合存在时跳过，不存在则创建）
    与 ensure_collection_exists() 完全一致的 HNSW 参数配置
    """
    if topic_collection_exists():
        logger.info(f"[Qdrant] 话题集合 '{TOPIC_COLLECTION_NAME}' 已存在，跳过创建")
        return

    from qdrant_client.models import Distance, VectorParams, HnswConfigDiff, OptimizersConfigDiff

    client = _get_client()
    client.create_collection(
        collection_name=TOPIC_COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=100,
            full_scan_threshold=10000,
        ),
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=10000,
        ),
    )
    logger.info(f"[Qdrant] 话题集合 '{TOPIC_COLLECTION_NAME}' 创建成功（dim={EMBEDDING_DIM}, HNSW m=16, ef=100）")


def get_topic_collection_info():
    """获取话题演化集合详细信息"""
    client = _get_client()
    return client.get_collection(collection_name=TOPIC_COLLECTION_NAME)


# ===========================
# 3. Embedding 生成
# ===========================

def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    调用 BGE-M3 对文本列表生成向量
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
# 4. 写入（Index）
# ===========================

def index_ai_result(result: dict) -> bool:
    """
    将单条 ai_results 写入 Qdrant

    Args:
        result: ai_results 表的单条记录（字典）

    Returns:
        True 成功，False 失败
    """
    try:
        title = result.get("title") or ""
        content = (result.get("content") or "")[:500]
        risk_level = result.get("risk_level") or ""
        core_issue = result.get("core_issue") or ""
        text_to_embed = (
            f"标题：{title}\n内容摘要：{content}\n"
            f"风险等级：{risk_level}\n核心问题：{core_issue}"
        )

        vectors = _embed_texts([text_to_embed])
        return _upsert_points([result], [vectors[0]]) == 1

    except Exception as e:
        logger.error(f"[RAG Index] post_id={result.get('post_id')} 索引异常: {e}")
        return False


def _upsert_points(results: list[dict], vectors: list[list[float]]) -> int:
    """
    将一批 ai_results + 对应向量写入 Qdrant

    qdrant-client 会自动处理 64 条上限分批，无需手动 chunking。

    Returns:
        成功写入数量
    """
    from qdrant_client.models import PointStruct

    client = _get_client()
    points = []
    for i in range(len(results)):
        r = results[i]
        post_id_str = str(r["post_id"])
        points.append(
            PointStruct(
                id=_post_id_to_qdrant_id(post_id_str),
                vector=vectors[i],
                payload={
                    "post_id": post_id_str,
                    "keyword": str(r.get("keyword") or ""),
                    "risk_level": str(r.get("risk_level") or "未知"),
                    "core_issue": str(r.get("core_issue") or "无"),
                    "report": str(r.get("report") or "无"),
                    "title": str(r.get("title") or "无标题"),
                    "content_preview": (r.get("content") or "")[:200],
                    "platform": str(r.get("platform") or ""),
                    "publish_time": str(r.get("publish_time") or ""),
                },
            )
        )

    operation_info = client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )
    # UpdateResult.status == "completed" 表示写入成功
    if getattr(operation_info, "status", None) == "completed":
        return len(points)
    return 0


QDRANT_UPSERT_BATCH_SIZE = 64  # Qdrant 单次 upsert 上限


def batch_index_ai_results(results: list[dict]) -> int:
    """
    批量写入多条 ai_results 到 Qdrant

    内部自动按 64 条分批 upsert。

    Returns:
        成功写入数量
    """
    if not results:
        return 0

    try:
        # 1. 构造所有待 embedding 的文本
        texts_to_embed = []
        for r in results:
            title = r.get("title") or ""
            content = (r.get("content") or "")[:500]
            risk_level = r.get("risk_level") or ""
            core_issue = r.get("core_issue") or ""
            texts_to_embed.append(
                f"标题：{title}\n内容摘要：{content}\n"
                f"风险等级：{risk_level}\n核心问题：{core_issue}"
            )

        # 2. 按 Qdrant 上限分批 embedding + upsert
        total_success = 0
        for i in range(0, len(results), QDRANT_UPSERT_BATCH_SIZE):
            batch_results = results[i:i + QDRANT_UPSERT_BATCH_SIZE]
            batch_texts = texts_to_embed[i:i + QDRANT_UPSERT_BATCH_SIZE]

            vectors_list = _embed_texts(batch_texts)
            count = _upsert_points(batch_results, vectors_list)
            total_success += count
            logger.info(
                f"[RAG Index] 批次 {i // QDRANT_UPSERT_BATCH_SIZE + 1}，"
                f"写入 {count}/{len(batch_results)} 条"
            )

        logger.info(f"[RAG Index] 批量写入完成：{total_success}/{len(results)} 条成功")
        return total_success

    except Exception as e:
        logger.error(f"[RAG Index] 批量写入异常: {e}")
        return 0


# ===========================
# 5. 检索（Retrieve）
# ===========================

def retrieve_similar_cases(
    keyword: str,
    query_text: str,
    top_k: int = 3,
) -> list[dict]:
    """
    检索与当前帖子最相似的历史案例

    策略：
    1. 对 query_text 生成 BGE-M3 向量
    2. 在 Qdrant 中按 keyword 精确过滤
    3. cosine 相似度排序，返回 top_k 条

    Returns:
        [
            {
                "post_id": str,
                "keyword": str,
                "risk_level": str,
                "core_issue": str,
                "report": str,
                "title": str,
                "score": float,
            },
            ...
        ]
    """
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # 1. 生成查询向量
        vectors = _embed_texts([query_text])
        query_vector = vectors[0]

        # 2. Qdrant 检索（使用 query_points API）
        client = _get_client()
        results = client.query_points(
            collection_name=COLLECTION_NAME,
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
            score_threshold=0.5,
            with_payload=True,
        )

        # 3. 格式化返回
        formatted = []
        # query_points 返回 QueryResponse，其 .points 是 ScoredPoint 列表
        points = getattr(results, 'points', []) or []
        for hit in points:
            p = hit.payload or {}
            formatted.append({
                "post_id": p.get("post_id", ""),
                "keyword": p.get("keyword", ""),
                "risk_level": p.get("risk_level", ""),
                "core_issue": p.get("core_issue", ""),
                "report": p.get("report", ""),
                "title": p.get("title", ""),
                "score": hit.score,
            })

        logger.info(f"[RAG Retrieve] keyword={keyword}, query={query_text[:30]}..., 返回 {len(formatted)} 条")
        return formatted

    except Exception as e:
        logger.warning(f"[RAG Retrieve] 检索失败: {e}")
        return []


# ===========================
# 6. 历史数据迁移
# ===========================

def migrate_all_history(limit: int = None, batch_size: int = 64) -> tuple[int, int]:
    """
    从 ai_results 表读取所有历史数据，批量写入 Qdrant

    Args:
        limit: 最多迁移条数（None = 全部）
        batch_size: 每批 embedding 调用数量（Qdrant 写入 SDK 自动分批到 64）

    Returns:
        (成功写入数, 总数)
    """
    import sqlite3
    from core.database import get_db_connection

    # 1. 确保集合存在
    ensure_collection_exists()

    # 2. 读取 ai_results
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if limit:
            cursor.execute(
                "SELECT * FROM ai_results ORDER BY create_time DESC LIMIT ?",
                (limit,),
            )
        else:
            cursor.execute("SELECT * FROM ai_results ORDER BY create_time DESC")
        rows = cursor.fetchall()

    results = [dict(r) for r in rows]
    total = len(results)

    if total == 0:
        logger.info("[Migration] ai_results 表为空，无数据需要迁移")
        return 0, 0

    logger.info(f"[Migration] 共找到 {total} 条历史舆情待迁移（batch_size={batch_size}）")

    # 3. 分批写入（embedding 按 batch_size 分批，Qdrant 写入自动处理 64 上限）
    success_count = 0
    for i in range(0, total, batch_size):
        batch = results[i : i + batch_size]
        count = batch_index_ai_results(batch)
        success_count += count
        logger.info(
            f"[Migration] 进度 {min(i + batch_size, total)}/{total}，成功写入 {success_count} 条"
        )

    logger.info(f"[Migration] 迁移完成！共写入 {success_count}/{total} 条")
    return success_count, total


def get_collection_stats() -> dict:
    """获取集合向量数量统计"""
    try:
        info = get_collection_info()
        # qdrant-client 版本差异，尝试多个可能的属性名
        vectors_count = getattr(info, "vectors_count", None) or getattr(info, "points_count", None)
        return {
            "vectors_count": vectors_count,
            "points_count": getattr(info, "points_count", None),
            "status": getattr(info, "status", None),
        }
    except Exception as e:
        logger.error(f"[Qdrant] 获取集合统计失败: {e}")
        return {}
