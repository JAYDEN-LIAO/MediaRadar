"""
视觉多模态 Agent

调用 Qwen-VL-Max 提取图片中的视觉证据，
用于图文融合分析，辅助 Screener 阶段复判。
"""

import os
import base64
import urllib.parse
import mimetypes

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import settings


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

vision_client = OpenAI(
    api_key=getattr(settings, "VISION_API_KEY", ""),
    base_url=getattr(settings, "VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_vision_llm(image_url: str, post_text: str = "", platform: str = "wb", post_id: str = ""):
    """
    调用 Qwen-VL-Max 提取图片视觉证据。

    Args:
        image_url: 图片 URL 或本地路径
        post_text: 帖子正文（可选，用于结合图片分析）
        platform: 平台标识
        post_id: 帖子 ID（用于定位小红书本地图片）

    Returns:
        视觉解析结果文本，失败时返回空字符串
    """
    from .prompt_templates import VISION_PROMPT

    clean_image_url = image_url.strip('"\'')
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

    # ── 尝试加载本地图片 ────────────────────────
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
                if not mime_type:
                    mime_type = "image/jpeg"
                final_image_url = f"data:{mime_type};base64,{base64_encoded}"
                logger.info(f"📸 成功加载本地图片 ({local_path})，准备发送至 Vision Agent...")
        else:
            logger.warning(f"⚠️ 本地图片未找到({local_path})，将尝试使用原始公网URL...")
    except Exception as e:
        logger.error(f"本地图片转换 Base64 异常: {e}")
    # ────────────────────────────────────────────

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
