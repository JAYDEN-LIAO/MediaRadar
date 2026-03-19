# backend/services/radar_service/llm_pipeline.py
import json
import sys
import os
import httpx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import settings
from .prompt_templates import SCREENER_PROMPT, ANALYST_PROMPT, DIRECTOR_PROMPT, CLUSTER_PROMPT

if not settings.DEEPSEEK_API_KEY or not settings.KIMI_API_KEY:
    logger.warning("Missing API Keys for either DeepSeek or Kimi. Please check your .env/config file.")

global_http_client = httpx.Client()

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

def clean_json_string(raw_text):
    """清理大模型返回的带有 markdown 标记的 JSON 字符串"""
    if not raw_text:
        return "{}"
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    return raw_text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(prompt, text, response_format="text", engine="deepseek"):
    """
    统一的 LLM 调用网关：实现多模型路由分发
    :param engine: "deepseek" 或 "kimi"，决定由谁来处理这个任务
    """
    if engine == "kimi":
        active_client = kimi_client
        active_model = settings.KIMI_MODEL
    else:
        active_client = deepseek_client
        active_model = settings.DEEPSEEK_MODEL

    try:
        kwargs = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ]
        }
        
        # 针对不同模型的特性分别设置参数
        if engine == "kimi":
            kwargs["temperature"] = 1  # Kimi 强制要求 temperature 必须为 1
        else:
            kwargs["temperature"] = 0.3 if response_format == "json" else 0.7
            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}

        response = active_client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content
        
        if response_format == "json":
            try:
                parsed = json.loads(clean_json_string(result))
            except json.JSONDecodeError:
                logger.error(f"[{engine.upper()}] JSON 解析失败，原始返回: {result}")
                return {}

            if isinstance(parsed, str):
                try: 
                    parsed = json.loads(parsed)
                except: 
                    return {}
            
            if not isinstance(parsed, dict) and not isinstance(parsed, list):
                return {}
            return parsed
            
        return result
        
    except Exception as e:
        logger.error(f"[{engine.upper()}] LLM call failed: {e}")
        raise e

def process_post(post, keyword):
    text_to_analyze = f"标题：{post['title']}\n内容：{post['content']}"
    
    screener_prompt = SCREENER_PROMPT.format(keyword=keyword)
    
    # 职能 1：初步筛查
    is_relevant_res = call_llm(screener_prompt, text_to_analyze, response_format="json", engine="deepseek")
    
    if not is_relevant_res.get("is_relevant", False):
        return {"status": "irrelevant"}
        
    analyst_prompt = ANALYST_PROMPT.format(keyword=keyword)
    
    # 职能 2：风险评级与情感分析
    analysis_res = call_llm(analyst_prompt, text_to_analyze, response_format="json", engine="deepseek")
    risk_level = analysis_res.get("risk_level", 0)
    sentiment = analysis_res.get("sentiment", "Neutral")
    
    if risk_level >= 3 or sentiment == "Negative":
        director_prompt = DIRECTOR_PROMPT.format(keyword=keyword)
        
        # 职能 3：总监级深度报告撰写
        report = call_llm(director_prompt, text_to_analyze, response_format="text", engine="kimi")
        
        return {
            "status": "alert",
            "risk_level": risk_level,
            "core_issue": analysis_res.get("core_issue", "未知"),
            "report": report
        }
        
    return {"status": "safe", "reason": "正常讨论，无明显风险"}

def cluster_related_posts(relevant_posts, keyword):
    if not relevant_posts:
        return []
        
    simplified_posts = []
    for p in relevant_posts:
        content_snippet = p['content'][:100].replace('\n', ' ')
        simplified_posts.append({
            "post_id": p['post_id'],
            "summary": f"标题:{p['title']} | 摘要:{content_snippet}"
        })
        
    cluster_prompt = CLUSTER_PROMPT.format(keyword=keyword)
    user_text = json.dumps(simplified_posts, ensure_ascii=False)
    
    clusters_res = call_llm(cluster_prompt, user_text, response_format="json", engine="kimi")
    
    if isinstance(clusters_res, dict):
        return clusters_res.get("clusters", [])
    elif isinstance(clusters_res, list):
        return clusters_res
    else:
        return []