# backend/core/config.py
import os
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

DATA_DIR = os.path.join(BACKEND_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    # ======== 配置1: Screener & Analyst (DeepSeek) ========
    ANALYST_API_KEY = os.getenv("ANALYST_API_KEY", "")
    ANALYST_BASE_URL = os.getenv("ANALYST_BASE_URL", "https://api.deepseek.com/v1").strip()
    ANALYST_MODEL = os.getenv("ANALYST_MODEL", "deepseek-chat")
    
    # ======== 配置2: Reviewer & Director (Kimi) ========
    REVIEWER_API_KEY = os.getenv("REVIEWER_API_KEY", "")
    REVIEWER_BASE_URL = os.getenv("REVIEWER_BASE_URL", "https://api.moonshot.cn/v1").strip()
    REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "kimi-k2.5")
    
    # ======== 配置3: The Cluster (向量聚类引擎) ========
    # 默认以硅基流动的免费 BGE-m3 API 为例，你可以在 .env 中覆盖它
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1").strip()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    # ======== 配置4: Vision Agent (多模态图片识别 - 通义千问 Qwen) ========
    # 默认使用阿里云百炼 (DashScope) 的 OpenAI 兼容接口
    VISION_API_KEY = os.getenv("VISION_API_KEY", "")
    VISION_BASE_URL = os.getenv("VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-max") 
    
    # ======== 系统路径配置 ========
    STATE_DB_PATH = os.getenv("STATE_DB_PATH", os.path.join(DATA_DIR, "radar_state.db"))
    CRAWLER_DB_PATH = os.getenv("CRAWLER_DB_PATH", os.path.join(BACKEND_DIR, "data", "sqlite_tables.db"))
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

settings = Settings()