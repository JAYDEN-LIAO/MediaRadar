# backend/services/radar_service/llm_pipeline.py
import json
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import settings
from .prompt_templates import SCREENER_PROMPT, ANALYST_PROMPT, DIRECTOR_PROMPT, CLUSTER_PROMPT

if not settings.LLM_API_KEY:
    raise ValueError("LLM_API_KEY not found in environment variables.")

client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

def clean_json_string(raw_text):
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    return raw_text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_llm(system_prompt, user_text, response_format="json"):
    truncated_text = user_text[:1500] if user_text else "无正文"
    
    api_kwargs = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下内容：\n\n{truncated_text}"}
        ],
        "temperature": 0.1
    }
    
    if response_format == "json":
        api_kwargs["response_format"] = {"type": "json_object"}
        
    response = client.chat.completions.create(**api_kwargs)
    content = response.choices[0].message.content
    
    if response_format == "json":
        try:
            cleaned_content = clean_json_string(content)
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.warning(f"JSON Parse failed, raw output: {content}")
            return {"is_relevant": False, "reason": "JSON解析失败", "risk_level": 0}
            
    return content

def process_post(post_data, keyword, skip_screener=True):
    text_to_analyze = f"【标题】: {post_data['title']}\n【正文】: {post_data['content']}"
    
    if not skip_screener:
        screener_prompt = SCREENER_PROMPT.format(keyword=keyword)
        screen_res = call_llm(screener_prompt, text_to_analyze, response_format="json")
        if not screen_res.get("is_relevant", False):
            return {"status": "ignored", "reason": screen_res.get("reason", "无关")}

    analyst_prompt = ANALYST_PROMPT.format(keyword=keyword)
    analysis_res = call_llm(analyst_prompt, text_to_analyze, response_format="json")
    risk_level = analysis_res.get("risk_level", 0)
    sentiment = analysis_res.get("sentiment", "Neutral")
    
    if risk_level >= 3 or sentiment == "Negative":
        director_prompt = DIRECTOR_PROMPT.format(keyword=keyword)
        report = call_llm(director_prompt, text_to_analyze, response_format="text")
        
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
    clusters = call_llm(cluster_prompt, user_text, response_format="json")
    
    if not isinstance(clusters, list):
        logger.warning("Clustering LLM output is not a list, degrading to single post mode.")
        return [{"topic_name": "零散舆情", "post_ids": [p['post_id'] for p in relevant_posts]}]
        
    return clusters