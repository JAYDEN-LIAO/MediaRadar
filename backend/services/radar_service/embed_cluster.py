"""
Embedding + HDBSCAN 聚类引擎

使用 BGE-M3 生成向量，HDBSCAN 自适应密度聚类，
将多个帖子按语义相似度归并为话题簇。
"""

import hdbscan

from core.logger import logger
from core.config import settings
from .llm_gateway import call_llm, embedding_client


def cluster_related_posts(relevant_posts, keyword):
    """
    将帖子列表通过向量聚类归并为话题簇。

    Args:
        relevant_posts: 待聚类的帖子列表
        keyword: 监控关键词

    Returns:
        List[dict]，每个 dict 包含 topic_name 和 post_ids
    """
    if len(relevant_posts) <= 2:
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]

    logger.info(f"[CLUSTER AGENT] 正在通过云端 API 对 {len(relevant_posts)} 条舆情进行聚类...")

    # ── 构造 embedding 输入文本 ──────────────────
    texts_to_embed = []
    for p in relevant_posts:
        title = p.get("title", "").strip()
        content = (p.get("content") or "").strip()
        if title and title != "无标题":
            texts_to_embed.append(f"{title}。{content[:150]}")
        else:
            texts_to_embed.append(f"内容：{content[:200]}" if content else "无标题")
    # ─────────────────────────────────────────────

    # ── BGE-M3 Embedding ──────────────────────────
    try:
        embed_res = embedding_client.embeddings.create(
            input=texts_to_embed,
            model=getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-m3")
        )
        embeddings = [data.embedding for data in embed_res.data]
    except Exception as e:
        logger.error(f"Embedding API 调用失败: {e}")
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]
    # ─────────────────────────────────────────────

    # ── HDBSCAN 本地聚类（自适应 eps，无需手动调参）──
    clustering = hdbscan.HDBSCAN(
        min_cluster_size=2,
        min_samples=2,
        metric='euclidean',
        cluster_selection_method='eom'
    ).fit(embeddings)
    # ─────────────────────────────────────────────

    clusters_dict = {}
    for idx, label in enumerate(clustering.labels_):
        clusters_dict.setdefault(label, []).append(relevant_posts[idx])

    final_clusters = []
    naming_system_prompt = "你是一个专业的舆情话题总结专家。请根据用户提供的多条网民发帖内容，用15个字以内提炼出一个核心舆情话题名称。只输出具体事件名称，不要带任何标点符号。"

    for label, posts in clusters_dict.items():
        # 噪音点（label=-1）每个单独成簇
        if label == -1:
            for p in posts:
                title = p.get("title", "").strip()
                content = (p.get("content") or "").strip()
                effective_title = title if title and title != "无标题" else (content[:15] if content else "无标题")
                final_clusters.append({"topic_name": effective_title, "post_ids": [p['post_id']]})
            continue

        # 构造样本供 LLM 生成话题名
        sample_parts = []
        for p in posts[:3]:
            title = p.get("title", "").strip()
            content = (p.get("content") or "").strip()
            if title and title != "无标题":
                sample_parts.append(f"- 标题：{title} | 内容：{content[:80]}")
            else:
                sample_parts.append(f"- 内容：{content[:100]}")
        sample_texts = "\n".join(sample_parts)

        topic_name = call_llm(
            prompt=naming_system_prompt,
            text=sample_texts,
            engine="kimi"
        ).strip('"').strip()

        if not topic_name or topic_name == "无标题":
            first_content = (posts[0].get("content") or "").strip()
            topic_name = first_content[:15] if first_content else "无标题"

        final_clusters.append({
            "topic_name": topic_name,
            "post_ids": [p['post_id'] for p in posts]
        })

    return final_clusters
