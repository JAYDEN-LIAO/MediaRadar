# yq_radar/llm_pipeline.py
import json
import re
import os
from dotenv import load_dotenv  # 需安装: pip install python-dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# ================= 配置初始化 =================
# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量读取配置（推荐：设置默认值 + 必填校验）
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# 安全校验：API Key 必填
if not LLM_API_KEY:
    raise ValueError("❌ 未找到 LLM_API_KEY，请检查 .env 文件是否正确配置")

client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

def clean_json_string(raw_text):
    """清洗大模型可能返回的带有 markdown 标记的 JSON 字符串"""
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
    """通用的 LLM 调用函数，带有自动重试机制（防网络抖动报错）"""
    # 截断文本，防止超长报错 (限制约1500字)
    truncated_text = user_text[:1500] if user_text else "无正文"
    
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下内容：\n\n{truncated_text}"}
        ],
        temperature=0.1 # 使用低温度保证结果的确定性和严谨性
    )
    
    content = response.choices[0].message.content
    
    if response_format == "json":
        try:
            cleaned_content = clean_json_string(content)
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            print(f"⚠️ JSON解析失败，原始输出: {content}")
            # 解析失败时返回默认安全格式
            return {"is_relevant": False, "reason": "JSON解析失败", "risk_level": 0}
            
    return content

def process_post(post_data, keyword, skip_screener=True):
    """多身份 AI 流水线核心逻辑 (适配聚合话题)"""
    text_to_analyze = f"【标题】: {post_data['title']}\n【正文】: {post_data['content']}"
    
    # --- 阶段 1：数据筛选员 (Screener) ---
    # 在微批处理架构中，过滤逻辑已前置，默认跳过此步骤节省 Token 和时间
    if not skip_screener:
        screener_prompt = f"""你是一个严谨的数据筛选员。
目标实体：【{keyword}】
请判断用户输入的内容是否真正在讨论该实体（排除重名、同城无关动态、或纯蹭热度的广告）。
请严格输出 JSON 格式（不要有多余的字）：
{{
    "is_relevant": true 或 false,
    "reason": "简短理由"
}}"""
        
        screen_res = call_llm(screener_prompt, text_to_analyze, response_format="json")
        if not screen_res.get("is_relevant", False):
            return {"status": "ignored", "reason": screen_res.get("reason", "无关")}

    # --- 阶段 2：舆情分析师 (Analyst) ---
    # 提示词微调：让 AI 意识到这可能是一组聚合话题
    analyst_prompt = f"""你是一位资深企业舆情分析师。请研判有关【{keyword}】的舆情内容（注意：这可能是一个聚合了多条相同话题的发帖集合）。
请严格输出 JSON 格式（不要有多余的字）：
{{
    "sentiment": "Positive" (正面) / "Neutral" (中立/客观) / "Negative" (负面/抱怨),
    "risk_level": <1到5的整数>, // 1:无风险 2:轻微吐槽 3:一般负面(需关注) 4:严重负面(纠纷/维权) 5:极危危机(暴雷/诈骗),
    "core_issue": "如果存在负面或风险，一句话概括核心问题；若无，填 '无'"
}}"""
    
    analysis_res = call_llm(analyst_prompt, text_to_analyze, response_format="json")
    risk_level = analysis_res.get("risk_level", 0)
    sentiment = analysis_res.get("sentiment", "Neutral")
    
    # --- 阶段 3：公关总监 (PR Director) - 仅高风险触发 ---
    if risk_level >= 3 or sentiment == "Negative":
        # 提示词微调：强调这是一个“事件简报”
        director_prompt = f"""你是一位公关总监。有关【{keyword}】的负面舆情被触发。该事件可能已在多个渠道发酵。
请根据用户的原文集合，写一段用于推送给高管的【紧急预警简报】。
要求：客观、严肃、一针见血。包含：事件概述、潜在的公关危机点。
字数：控制在 100 字以内，纯文本输出，不要使用 Markdown 格式。"""
        
        report = call_llm(director_prompt, text_to_analyze, response_format="text")
        
        return {
            "status": "alert",
            "risk_level": risk_level,
            "core_issue": analysis_res.get("core_issue", "未知"),
            "report": report
        }
        
    return {"status": "safe", "reason": "正常讨论，无明显风险"}

def cluster_related_posts(relevant_posts, keyword):
    """
    话题聚类器：将多条帖子按讨论的'核心事件'进行分组聚合
    :param relevant_posts: 列表，包含经过筛选员判断为相关的帖子字典
    """
    if not relevant_posts:
        return []
        
    # 为了防止上下文超限，我们只提取 ID、标题和正文前100字给大模型聚类
    simplified_posts = []
    for p in relevant_posts:
        content_snippet = p['content'][:100].replace('\n', ' ')
        simplified_posts.append({
            "post_id": p['post_id'],
            "summary": f"标题:{p['title']} | 摘要:{content_snippet}"
        })
        
    cluster_prompt = f"""你是一个舆情话题聚类专家。
请阅读以下关于【{keyword}】的近期动态列表，将讨论【同一个具体事件/问题/槽点】的帖子聚合在一起。
如果是独立的日常发帖，也允许单独成为一个话题。

请严格按以下 JSON 格式输出（不要有 markdown 标记）：
[
    {{
        "topic_name": "一句话概括这个聚合话题（例如：App闪退问题）",
        "post_ids": ["帖子ID_1", "帖子ID_2"]
    }},
    ...
]
"""
    
    # 将简化后的列表转为 JSON 文本喂给 LLM
    user_text = json.dumps(simplified_posts, ensure_ascii=False)
    
    # 注意：这里可能返回的是 list，所以 call_llm 里的 json.loads 能直接解析
    clusters = call_llm(cluster_prompt, user_text, response_format="json")
    
    # 容错：如果 LLM 返回的不是列表，给个保底策略（全部归为单独话题）
    if not isinstance(clusters, list):
        print("⚠️ 聚类 LLM 返回格式异常，降级为单帖单话题")
        return [{"topic_name": "零散舆情", "post_ids": [p['post_id'] for p in relevant_posts]}]
        
    return clusters