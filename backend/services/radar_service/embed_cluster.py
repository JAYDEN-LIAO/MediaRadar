"""
Embedding + HDBSCAN 聚类引擎

使用 BGE-M3 生成向量，HDBSCAN 自适应密度聚类，
将多个帖子按语义相似度归并为话题簇。
"""

import hdbscan
import numpy as np
import umap
from typing import List

from core.logger import get_logger

logger = get_logger("radar.cluster")
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
        return [
            {"topic_name": p.get("generated_title") or (p.get('title') or "无标题")[:15],
             "post_ids": [p['post_id']],
             "posts": [p]}
            for p in relevant_posts
        ]

    logger.info(f"[CLUSTER AGENT] 正在通过云端 API 对 {len(relevant_posts)} 条舆情进行聚类...")

    # ── 构造 embedding 输入文本 ──────────────────
    texts_to_embed = []
    for p in relevant_posts:
        # 优先使用 LLM 生成的标准化标题，其次使用原始标题
        generated_title = p.get("generated_title", "").strip()
        original_title = p.get("title", "").strip()
        content = (p.get("content") or "").strip()

        if generated_title:
            # LLM 生成的标准化标题：语义标准化 + 关键词提纯
            texts_to_embed.append(f"{generated_title}。{content[:150]}")
        elif original_title and original_title != "无标题":
            texts_to_embed.append(f"{original_title}。{content[:150]}")
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
        return [
            {"topic_name": p.get("generated_title") or p['title'][:15],
             "post_ids": [p['post_id']],
             "posts": [p]}
            for p in relevant_posts
        ]
    # ─────────────────────────────────────────────

    # ── UMAP 降维 + HDBSCAN 聚类 ─────────────────
    # 高维(1024d) → 低维(50d/30d/10d)，改善密度估计稳定性
    n_samples = len(embeddings)
    n_components = min(50, max(2, n_samples - 1))  # UMAP 要求 n_components <= n_samples - 1

    logger.info(f"[CLUSTER] UMAP降维: 1024d → {n_components}d")

    reducer = umap.UMAP(
        n_components=n_components,
        metric='cosine',          # BGE-M3 使用 cosine 相似度
        random_state=42,
        n_neighbors=min(5, n_samples - 1),  # 邻居数不超过样本数-1
    )
    try:
        embeddings_reduced = reducer.fit_transform(embeddings)
    except Exception as e:
        logger.warning(f"[CLUSTER] UMAP降维失败，使用原始embedding: {e}")
        embeddings_reduced = embeddings

    clustering = hdbscan.HDBSCAN(
        min_cluster_size=2,
        min_samples=2,
        metric='euclidean',
        cluster_selection_method='eom'
    ).fit(embeddings_reduced)
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
                # 优先使用 LLM 生成的标准化标题
                generated_title = p.get("generated_title", "").strip()
                original_title = p.get("title", "").strip()
                content = (p.get("content") or "").strip()
                if generated_title:
                    effective_title = generated_title
                elif original_title and original_title != "无标题":
                    effective_title = original_title
                else:
                    effective_title = content[:15] if content else "无标题"
                final_clusters.append({
                    "topic_name": effective_title,
                    "post_ids": [p['post_id']],
                    "posts": [p]      # 包含 posts，供 merge_similar_clusters 使用
                })
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

        topic_name_result = call_llm(
            prompt=naming_system_prompt,
            text=sample_texts,
            engine="kimi"
        )
        topic_name = (topic_name_result.data if topic_name_result.success and topic_name_result.data else "").strip('"').strip()

        if not topic_name or topic_name == "无标题":
            first_content = (posts[0].get("content") or "").strip()
            topic_name = first_content[:15] if first_content else "无标题"

        final_clusters.append({
            "topic_name": topic_name,
            "post_ids": [p['post_id'] for p in posts],
            "posts": posts               # 包含 posts，供 merge_similar_clusters 使用
        })

    return final_clusters


# ============================================================
# 后处理：同类话题合并层（Union-Find 安全网）
# ============================================================

def _get_cluster_keywords(cluster_posts: List[dict]) -> dict:
    """
    为单个簇生成关键词标签（实体词 + 事件类型）。
    返回格式：{"entities": [...], "event_type": "..."}
    """
    if not cluster_posts:
        return {"entities": [], "event_type": ""}

    # 构造样本文本供 LLM 抽取关键词
    sample_parts = []
    for p in cluster_posts[:5]:
        title = p.get("generated_title") or p.get("title", "").strip()
        content = (p.get("content") or "").strip()
        if title and title != "无标题":
            sample_parts.append(f"标题：{title}，内容：{content[:100]}")
        else:
            sample_parts.append(f"内容：{content[:120]}")

    sample_texts = "\n".join(sample_parts)

    keyword_prompt = """你是一个舆情关键词抽取专家。从以下帖子内容中抽取：
1. 核心实体词（如：品牌名、人名、产品名）- 最多5个
2. 事件类型（如：侵权纠纷、假唱争议、服务投诉、产品质量问题）- 只取1个

请严格输出 JSON 格式：
{{
    "entities": ["实体词1", "实体词2", ...],
    "event_type": "事件类型"
}}

帖子内容：
"""

    try:
        result = call_llm(
            prompt=keyword_prompt,
            text=sample_texts,
            response_format="json",
            engine="kimi"
        )
        data = result.data if result.success and result.data is not None else {}
        entities = data.get("entities", [])
        event_type = data.get("event_type", "")
        return {"entities": entities, "event_type": event_type}
    except Exception as e:
        logger.warning(f"[Cluster Merge] 关键词抽取失败: {e}")
        # 降级：使用原始标题作为关键词
        titles = [p.get("generated_title") or p.get("title", "") for p in cluster_posts[:3]]
        return {"entities": titles, "event_type": ""}


def _calculate_topic_similarity(topic_a: dict, topic_b: dict) -> float:
    """
    判断两个话题是否属于同一事件。
    综合得分 > MERGE_THRESHOLD 则合并。

    判断依据（加权）：
    1. 实体重叠度（Jaccard）
    2. 事件类型相似度
    3. generated_title 相同/高度相似（字面级匹配）
    """
    MERGE_THRESHOLD = 0.45

    entities_a = set(topic_a.get("entities", []))
    entities_b = set(topic_b.get("entities", []))
    intersection = entities_a & entities_b
    union = entities_a | entities_b
    jaccard = len(intersection) / len(union) if union else 0.0

    # 实体共现加分（交集非空）
    entity_boost = 1.0 if intersection else 0.0

    # 事件类型相同
    event_a = topic_a.get("event_type", "").strip()
    event_b = topic_b.get("event_type", "").strip()
    event_match = 1.0 if (event_a and event_a == event_b) else 0.0

    # generated_title 字面匹配（同类帖子应该生成相同的标准化标题）
    title_a = topic_a.get("generated_title", "").strip()
    title_b = topic_b.get("generated_title", "").strip()
    if title_a and title_b:
        # 简单粗暴：标题相同/高度相似（包含相同关键词）→ 合并
        title_similarity = 1.0 if title_a == title_b else (
            0.8 if title_a[:10] == title_b[:10] else 0.0
        )
    else:
        title_similarity = 0.0

    # 综合得分：标题匹配最重要，其次实体重叠，再次事件类型
    score = 0.5 * title_similarity + 0.3 * jaccard + 0.1 * entity_boost + 0.1 * event_match
    return score


def _merge_clusters_of_group(clusters_group: List[dict]) -> dict:
    """
    将多个同类簇合并为一个簇。
    - 拼接所有 post_ids
    - 拼接所有 posts
    - 用 LLM 生成新的统一话题名
    """
    if len(clusters_group) == 1:
        return clusters_group[0]

    # 收集所有帖子
    all_posts = []
    for c in clusters_group:
        all_posts.extend(c.get("posts", []))

    # 收集所有 post_ids（去重）
    all_pids = list({pid for c in clusters_group for pid in c.get("post_ids", [])})

    # 用 LLM 生成统一话题名（基于所有帖子的 generated_title）
    titles = [p.get("generated_title") or p.get("title", "") for p in all_posts[:5] if p.get("generated_title")]
    unique_titles = list(dict.fromkeys(titles))  # 去重保持顺序

    naming_prompt = (
        "你是一个专业的舆情话题总结专家。"
        "以下是多条关于同一事件的帖子标题（已由LLM标准化），"
        "请用15个字以内提炼出一个统一的核心舆情话题名称。"
        "只输出话题名称，不要带任何标点符号或解释。\n\n"
    )
    if unique_titles:
        titles_text = "、".join(unique_titles[:5])
        naming_prompt += f"标题列表：{titles_text}"
    else:
        # 降级：用内容摘要
        contents = [p.get("content", "")[:50] for p in all_posts[:3]]
        naming_prompt += "内容摘要：" + " | ".join(contents)

    try:
        unified_name_result = call_llm(prompt=naming_prompt, text="", engine="kimi")
        unified_name = (unified_name_result.data if unified_name_result.success and unified_name_result.data else "").strip('"').strip()
        if not unified_name:
            unified_name = unique_titles[0][:15] if unique_titles else all_posts[0].get("content", "")[:15]
    except Exception:
        unified_name = unique_titles[0][:15] if unique_titles else all_posts[0].get("content", "")[:15]

    return {
        "topic_name": unified_name,
        "post_ids": all_pids,
        "posts": all_posts,
    }


def merge_similar_clusters(clusters: List[dict]) -> List[dict]:
    """
    对 HDBSCAN 输出的多个簇进行同类合并（最终安全网）。

    策略：并查集（Union-Find）
    - 初始每个簇是独立集合
    - 两两比较，综合得分 > MERGE_THRESHOLD → 合并
    - 最终返回合并后的簇列表

    Args:
        clusters: HDBSCAN 输出的簇列表，每个 dict 包含 topic_name, post_ids, posts

    Returns:
        合并后的簇列表
    """
    if len(clusters) <= 1:
        return clusters

    logger.info(f"[Cluster Merge] 开始合并检查，共 {len(clusters)} 个原始簇")

    # Step 1：为每个簇生成关键词（实体 + 事件类型）
    cluster_meta = []
    for c in clusters:
        posts = c.get("posts", [])
        keyword_info = _get_cluster_keywords(posts)
        generated_titles = [p.get("generated_title", "") for p in posts if p.get("generated_title")]
        cluster_meta.append({
            "cluster": c,
            "entities": keyword_info.get("entities", []),
            "event_type": keyword_info.get("event_type", ""),
            "generated_titles": generated_titles,
        })

    # Step 2：并查集初始化
    n = len(cluster_meta)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # 路径压缩
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Step 3：两两比较，触发合并
    MERGE_THRESHOLD = 0.45

    for i in range(n):
        for j in range(i + 1, n):
            meta_i = cluster_meta[i]
            meta_j = cluster_meta[j]

            topic_i = {
                "entities": meta_i["entities"],
                "event_type": meta_i["event_type"],
                "generated_title": meta_i["generated_titles"][0] if meta_i["generated_titles"] else "",
            }
            topic_j = {
                "entities": meta_j["entities"],
                "event_type": meta_j["event_type"],
                "generated_title": meta_j["generated_titles"][0] if meta_j["generated_titles"] else "",
            }

            score = _calculate_topic_similarity(topic_i, topic_j)
            if score > MERGE_THRESHOLD:
                union(i, j)

    # Step 4：按并查集根节点分组
    from collections import defaultdict
    groups = defaultdict(list)
    for i, meta in enumerate(cluster_meta):
        root = find(i)
        groups[root].append(meta["cluster"])

    # Step 5：合并每个组
    merged = []
    for group in groups.values():
        merged_cluster = _merge_clusters_of_group(list(group))
        merged.append(merged_cluster)

    logger.info(f"[Cluster Merge] 合并完成：{len(clusters)} → {len(merged)} 个簇")
    return merged
