# backend/services/radar_service/llm_pipeline.py
import json
import sys
import os
import httpx
import numpy as np
from sklearn.cluster import DBSCAN
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import settings
from .prompt_templates import SCREENER_PROMPT, ANALYST_PROMPT, DIRECTOR_PROMPT, REVIEWER_PROMPT

global_http_client = httpx.Client()

# 初始化各个大模型 Client
deepseek_client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY, 
    base_url=settings.DEEPSEEK_BASE_URL,
    http_client=global_http_client
)
kimi_client = OpenAI(
    api_key=settings.KIMI_API_KEY, 
    base_url=settings.KIMI_BASE_URL,
    http_client=global_http_client
)
embedding_client = OpenAI(
    api_key=getattr(settings, "EMBEDDING_API_KEY", ""), 
    base_url=getattr(settings, "EMBEDDING_BASE_URL", ""),
    http_client=global_http_client
)
vision_client = OpenAI(
    api_key=getattr(settings, "VISION_API_KEY", ""), 
    base_url=getattr(settings, "VISION_BASE_URL", ""),
    http_client=global_http_client
)

# ==========================================
# 定义 Pydantic 数据契约 (Data Schemas)
# ==========================================
class ScreenerResult(BaseModel):
    analysis_process: str = Field(default="", description="模型的思考分析过程")
    is_relevant: bool = Field(default=False, description="是否相关")
    matched_keyword: str = Field(default="", description="匹配到的具体实体名")
    reason: str = Field(default="", description="判断理由")

class AnalystResult(BaseModel):
    analysis_process: str = Field(default="", description="风险评估的思考过程")
    sentiment: str = Field(default="Neutral", description="情感倾向")
    risk_level: int = Field(default=1, description="风险等级1-5")
    core_issue: str = Field(default="无", description="核心问题概括")

class ReviewerResult(BaseModel):
    analysis_process: str = Field(default="", description="交叉验证思考过程")
    is_confirmed: bool = Field(default=False, description="是否同意高风险")
    adjusted_risk_level: int = Field(default=2, description="调整后的风险等级")
    reason: str = Field(default="", description="维持或驳回的理由")

# ==========================================
# 核心大模型调用网关
# ==========================================
def clean_json_string(raw_text):
    """清理模型返回的 Markdown JSON 标签，已重写以避免前端解析截断"""
    if not raw_text: 
        return "{}"
    res = raw_text.strip()
    res = res.replace("```json", "")
    res = res.replace("```", "")
    return res.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt, text, response_format="text", engine="deepseek", pydantic_model=None):
    active_client = kimi_client if engine == "kimi" else deepseek_client
    active_model = settings.KIMI_MODEL if engine == "kimi" else settings.DEEPSEEK_MODEL

    try:
        kwargs = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 1 if engine == "kimi" else (0.3 if response_format == "json" else 0.7)
        }
        
        if engine != "kimi" and response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = active_client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content
        
        if response_format != "json": 
            return result

        try:
            parsed_dict = json.loads(clean_json_string(result))
        except json.JSONDecodeError:
            logger.error(f"[{engine.upper()}] JSON 解析失败，原始返回: {result}")
            return {}

        if pydantic_model:
            try:
                validated_data = pydantic_model(**parsed_dict)
                return validated_data.model_dump() 
            except ValidationError as e:
                logger.error(f"[{engine.upper()}] Pydantic 字段校验失败: {e}")
                return pydantic_model().model_dump()
        
        return parsed_dict
        
    except Exception as e:
        logger.error(f"[{engine.upper()}] LLM call failed: {e}")
        raise e

# ==========================================
# Agent +1: 视觉多模态分析师 (Vision Agent)
# ==========================================
def call_vision_llm(image_url: str):
    prompt = "请提取图片中的核心文字内容，并简要判断是否包含针对企业的负面投诉、系统报错或极端情绪。"
    try:
        response = vision_client.chat.completions.create(
            model=getattr(settings, "VISION_MODEL", "glm-4v"),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"[VISION AGENT] 视觉模型调用失败: {e}")
        return ""

# ==========================================
# Agent 5: 聚类引擎 (The Cluster)
# ==========================================
def cluster_related_posts(relevant_posts, keyword):
    if len(relevant_posts) <= 2:
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]

    logger.info(f"[CLUSTER AGENT] 正在通过云端 API 对 {len(relevant_posts)} 条舆情进行聚类...")
    texts_to_embed = [f"{p['title']}。{p['content'][:150]}" for p in relevant_posts]
    
    try:
        embed_res = embedding_client.embeddings.create(
            input=texts_to_embed,
            model=getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-m3")
        )
        embeddings = [data.embedding for data in embed_res.data]
    except Exception as e:
        logger.error(f"Embedding API 调用失败: {e}")
        return [{"topic_name": p['title'][:15], "post_ids": [p['post_id']]} for p in relevant_posts]
    
    # DBSCAN 本地聚类
    clustering = DBSCAN(eps=0.5, min_samples=2, metric='cosine').fit(embeddings)
    
    clusters_dict = {}
    for idx, label in enumerate(clustering.labels_):
        clusters_dict.setdefault(label, []).append(relevant_posts[idx])
        
    final_clusters = []
    naming_prompt_template = "你是一个舆情专家。请根据以下几条网民发帖的内容，用15个字以内提炼一个核心舆情话题名称。只输出名称，不要标点：\n{texts}"
    
    for label, posts in clusters_dict.items():
        if label == -1:
            for p in posts:
                final_clusters.append({"topic_name": p['title'][:15], "post_ids": [p['post_id']]})
            continue
            
        sample_texts = "\n".join([f"- {p['title']} | {p['content'][:50]}" for p in posts[:3]])
        topic_name = call_llm(naming_prompt_template.format(texts=sample_texts), "", engine="kimi").strip('\"')
        
        final_clusters.append({
            "topic_name": topic_name if topic_name else posts[0]['title'][:15],
            "post_ids": [p['post_id'] for p in posts]
        })

    return final_clusters

# ==========================================
# 核心管线：风险定性、复核与报告生成 (Analyst -> Reviewer -> Director)
# ==========================================
def analyze_and_report(mock_post, keyword):
    text_to_analyze = f"标题：{mock_post['title']}\n内容：{mock_post['content']}"
    
    # [Agent 2] The Analyst (DeepSeek)
    analyst_prompt = ANALYST_PROMPT.format(keyword=keyword)
    analysis_res = call_llm(
        analyst_prompt, text_to_analyze, response_format="json", 
        engine="deepseek", pydantic_model=AnalystResult
    )
    
    risk_level = analysis_res.get("risk_level", 1)
    sentiment = analysis_res.get("sentiment", "Neutral")
    core_issue = analysis_res.get("core_issue", "未知")
    
    if risk_level >= 3 or sentiment == "Negative":
        # [Agent 3] The Reviewer (Kimi 交叉验证)
        logger.info(f"[REVIEWER AGENT] 触发高危预警 (Level {risk_level})，移交异源模型进行交叉验证...")
        reviewer_prompt = REVIEWER_PROMPT.format(keyword=keyword, initial_risk=risk_level)
        review_res = call_llm(
            reviewer_prompt, text_to_analyze, response_format="json", 
            engine="kimi", pydantic_model=ReviewerResult
        )
        
        if not review_res.get("is_confirmed", False):
            risk_level = review_res.get("adjusted_risk_level", 2)
            reason = review_res.get("reason", "降级处理")
            logger.info(f"⚠️ [REVIEWER AGENT] 驳回高危判定！已降级为 Level {risk_level}。理由: {reason}")
            if risk_level < 3:
                return {"status": "safe", "risk_level": risk_level, "reason": f"Reviewer复核已降级: {reason}"}
        else:
            logger.info("🚨 [REVIEWER AGENT] 确认高风险真实有效，允许放行！")

        # [Agent 4] The Director (Kimi 报告生成)
        director_prompt = DIRECTOR_PROMPT.format(keyword=keyword)
        report = call_llm(director_prompt, text_to_analyze, response_format="text", engine="kimi")
        
        return {
            "status": "alert",
            "risk_level": risk_level,
            "core_issue": core_issue,
            "report": report
        }
        
    return {"status": "safe", "reason": "正常讨论，无明显风险", "risk_level": risk_level}