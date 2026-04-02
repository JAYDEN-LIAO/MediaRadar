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

    # ======== 配置5: Qdrant 向量数据库（RAG 知识库） ========
    QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "yq_history")

    # ======== 配置6: Qdrant 话题演化追踪集合 ========
    TOPIC_COLLECTION = os.getenv("TOPIC_COLLECTION", "topic_evolution")

    # ======== 系统路径配置 ========
    STATE_DB_PATH = os.getenv("STATE_DB_PATH", os.path.join(DATA_DIR, "radar_state.db"))
    CRAWLER_DB_PATH = os.getenv("CRAWLER_DB_PATH", os.path.join(BACKEND_DIR, "data", "sqlite_tables.db"))
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

    # ======== 日志配置 ========
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # text | json
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    LOG_USE_UTC = os.getenv("LOG_USE_UTC", "false").lower() == "true"

settings = Settings()