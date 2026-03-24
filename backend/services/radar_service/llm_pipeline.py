# backend/services/radar_service/llm_pipeline.py
import json
import sys
import os
import httpx
import numpy as np
import base64
import urllib.parse
import mimetypes
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
from .prompt_templates import SCREENER_PROMPT, ANALYST_PROMPT, DIRECTOR_PROMPT, REVIEWER_PROMPT, VISION_PROMPT

global_http_client = httpx.Client()

# 初始化各个大模型 Client
deepseek_client = OpenAI(
    api_key=settings.ANALYST_API_KEY, 
    base_url=settings.ANALYST_BASE_URL,
    http_client=global_http_client
)
kimi_client = OpenAI(
    api_key=settings.REVIEWER_API_KEY, 
    base_url=settings.REVIEWER_BASE_URL,
    http_client=global_http_client
)
embedding_client = OpenAI(
    api_key=getattr(settings, "EMBEDDING_API_KEY", ""), 
    base_url=getattr(settings, "EMBEDDING_BASE_URL", ""),
    http_client=global_http_client
)
vision_client = OpenAI(
    api_key=getattr(settings, "VISION_API_KEY", ""), 
    base_url=getattr(settings, "VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
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
    active_model = settings.REVIEWER_MODEL if engine == "kimi" else settings.ANALYST_MODEL

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
def call_vision_llm(image_url: str, post_text: str = "", platform: str = "wb", post_id: str = ""):
    clean_image_url = image_url.strip('"\' ')
    prompt = VISION_PROMPT.format(text_content=post_text if post_text else "无配文")
    final_image_url = clean_image_url

    platform_dir_map = {
        "wb": "weibo",
        "dy": "douyin",
        "bili": "bilibili",
        "xhs": "xhs",
        "ks": "kuaishou"
    }
    dir_name = platform_dir_map.get(platform.lower(), platform.lower())
    
    try:
        if platform.lower() == "xhs" and post_id:
            local_path = os.path.join(BASE_DIR, "services", "crawler_service", "data", dir_name, "images", str(post_id), "0.jpg")
        else:
            filename = os.path.basename(urllib.parse.urlparse(clean_image_url).path)
            local_path = os.path.join(BASE_DIR, "services", "crawler_service", "data", dir_name, "images", filename)
        
        if os.path.exists(local_path):
            with open(local_path, "rb") as image_file:
                base64_encoded = base64.b64encode(image_file.read()).decode('utf-8')
                mime_type, _ = mimetypes.guess_type(local_path)
                if not mime_type: mime_type = "image/jpeg"
                final_image_url = f"data:{mime_type};base64,{base64_encoded}"
                logger.info(f"📸 成功加载本地图片 ({local_path})，准备发送至 Vision Agent...")
        else:
            logger.warning(f"⚠️ 本地图片未找到({local_path})，将尝试使用原始公网URL...")
    except Exception as e:
        logger.error(f"本地图片转换 Base64 异常: {e}")

    try:
        logger.info(f"👉 [VISION INPUT] 传给视觉模型的提示词: {prompt}")
        
        response = vision_client.chat.completions.create(
            model=getattr(settings, "VISION_MODEL", "qwen-vl-max"), 
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": final_image_url}}
                ]
            }],
            max_tokens=300
        )
        result_text = response.choices[0].message.content.strip()
        logger.info(f"💡 [VISION OUTPUT] 视觉解析结果: {result_text}")
        return result_text
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
    naming_system_prompt = "你是一个专业的舆情话题总结专家。请根据用户提供的多条网民发帖内容，用15个字以内提炼出一个核心舆情话题名称。只输出具体事件名称，不要带任何标点符号。"
    
    for label, posts in clusters_dict.items():
        if label == -1:
            for p in posts:
                final_clusters.append({"topic_name": p['title'][:15], "post_ids": [p['post_id']]})
            continue
            
        sample_texts = "\n".join([f"- {p['title']} | {p['content'][:50]}" for p in posts[:3]])
        
        topic_name = call_llm(
            prompt=naming_system_prompt, 
            text=sample_texts, 
            engine="kimi"
        ).strip('\"')
        
        final_clusters.append({
            "topic_name": topic_name if topic_name else posts[0]['title'][:15],
            "post_ids": [p['post_id'] for p in posts]
        })

    return final_clusters

# ==========================================
# 核心管线：风险定性、复核与报告生成 (Analyst -> Reviewer -> Director)
# ==========================================
def analyze_and_report(mock_post, keyword):
    # 🌟 动态获取该关键字的监控等级 (局部导入防止循环引用)
    from .main import MONITOR_KEYWORD_LEVELS
    sensitivity = MONITOR_KEYWORD_LEVELS.get(keyword, "balanced")
    
    # 🌟 根据等级匹配不同的最终复核指令
    if sensitivity == "aggressive":
        level_instruction = "- 激进放行指令：高度敏感！由于该品牌当前处于重点监控期，**禁止轻易降级**！只要是明确的负面吐槽（哪怕是“吃出异物”、“服务态度极差”这种单点客诉），也有引爆全网的风险，请维持高风险等级（>=3），宁可误报不可漏报！"
    elif sensitivity == "conservative":
        level_instruction = "- 保守降级指令：极度严格！把所有“客服回复慢”、“App稍微有点卡”等单点问题统统强制驳回，降级为 1-2 级。只有权威媒体介入、重大违规、群体维权、资金安全等极其严重的灾难级事件才允许维持 3 级及以上！"
    else:
        level_instruction = "- 平衡复核指令：把“回复慢”、“轻微吐槽”等单点客诉降级为 1-2 级。确认为“群体性维权”、“重大违规”、“高管丑闻”、“大V点名”等可能引发大面积传播的事件时，才维持 3 级及以上。"

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
    current_topic_name = mock_post.get("title", "未知话题")

    if risk_level >= 3 or sentiment == "Negative":
        # [Agent 3] The Reviewer (Kimi 交叉验证)
        logger.warning(f"🚨 [ANALYST 判定] 话题 {current_topic_name} 触发预警！判定等级: Level {risk_level} | 情感倾向: {sentiment} | 核心问题: {core_issue}")
        logger.info(f"[REVIEWER AGENT] 触发高危预警 (Level {risk_level})，监控等级[{sensitivity}]，移交异源模型进行交叉验证...")
        
        # 🌟 注入带有监控等级的动态指令
        reviewer_prompt = REVIEWER_PROMPT.format(
            keyword=keyword, 
            initial_risk=risk_level,
            sensitivity=sensitivity,
            level_instruction=level_instruction
        )
        
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