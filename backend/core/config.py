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
    # ======== 默认模型配置（所有 Agent 的兜底配置）=======
    DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY", "")
    DEFAULT_BASE_URL = os.getenv("DEFAULT_BASE_URL", "https://api.deepseek.com/v1").strip()
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-chat")

    # ======== 配置1: 分析员 Agent ========
    ANALYST_API_KEY = os.getenv("ANALYST_API_KEY", "")
    ANALYST_BASE_URL = os.getenv("ANALYST_BASE_URL", "").strip()
    ANALYST_MODEL = os.getenv("ANALYST_MODEL", "").strip()

    # ======== 配置2: 复核员 Agent ========
    REVIEWER_API_KEY = os.getenv("REVIEWER_API_KEY", "")
    REVIEWER_BASE_URL = os.getenv("REVIEWER_BASE_URL", "").strip()
    REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "").strip()

    # ======== 配置 (v2 修复 #2.1): Agent 智能体（分析/对话助手） ========
    AGENT_API_KEY = os.getenv("AGENT_API_KEY", "").strip()
    AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "").strip()
    AGENT_MODEL = os.getenv("AGENT_MODEL", "").strip()

    # ======== 配置3: 向量引擎 ========
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "").strip()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "").strip()

    # ======== 配置4: 视觉引擎 ========
    VISION_API_KEY = os.getenv("VISION_API_KEY", "")
    VISION_BASE_URL = os.getenv("VISION_BASE_URL", "").strip()
    VISION_MODEL = os.getenv("VISION_MODEL", "").strip()

    # ======== 配置5: Qdrant 向量数据库（RAG 知识库） ========
    QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "yq_history")

    # ======== 配置6: Qdrant 话题演化追踪集合 ========
    TOPIC_COLLECTION = os.getenv("TOPIC_COLLECTION", "topic_evolution")

    # ======== Agent 配置 ========
    AGENT_MCP_ENABLED = os.getenv("AGENT_MCP_ENABLED", "false").lower() == "true"
    AGENT_MCP_TRANSPORT = os.getenv("AGENT_MCP_TRANSPORT", "http").strip()
    AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "6"))
    AGENT_MEMORY_TTL_DAYS = int(os.getenv("AGENT_MEMORY_TTL_DAYS", "90"))
    AGENT_TOKEN_BUDGET = int(os.getenv("AGENT_TOKEN_BUDGET", "1500"))
    AGENT_REFLECTION_ENABLED = os.getenv("AGENT_REFLECTION_ENABLED", "true").lower() == "true"
    AGENT_SELF_HEALING_ENABLED = os.getenv("AGENT_SELF_HEALING_ENABLED", "true").lower() == "true"

    # ======== 系统路径配置 ========
    STATE_DB_PATH = os.getenv("STATE_DB_PATH", os.path.join(DATA_DIR, "radar_state.db"))
    CRAWLER_DB_PATH = os.getenv("CRAWLER_DB_PATH", os.path.join(BACKEND_DIR, "data", "sqlite_tables.db"))
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

    # ======== 环境标识（用于 CORS 等配置按环境区分）=======
    ENV = os.getenv("ENV", "dev").lower()  # dev | prod
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").strip()  # 逗号分隔

    # ======== API 认证配置 ========
    API_KEYS = os.getenv("API_KEYS", "")

    # ======== WS4: JWT 认证配置 ========
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-prod-please-32bytes").strip()
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
    JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    # ======== WS4: OAuth 配置（v2 上线时填真实值）=======
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "").strip()
    WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "").strip()
    OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "https://mediaradar.jaydennn.xyz").strip()

    # ======== 日志配置 ========
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # text | json
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    LOG_USE_UTC = os.getenv("LOG_USE_UTC", "false").lower() == "true"

settings = Settings()

from core.agent_memory_db import init_db as _  # Agent 记忆库初始化


def update_llm_config(agent: str, config: dict) -> bool:
    """
    更新指定 Agent 的 LLM 配置（仅内存生效，不再写入 .env 文件）。
    agent: "default" | "analyst" | "reviewer" | "embedding" | "vision" | "agent"

    注意：此函数只更新运行时 settings 对象。
    如需持久化，请手动编辑 .env 文件，或通过前端设置页保存。
    """
    _BAD_VALUES = {"test", "sk-test", "", "gpt-4"}

    prefix_map = {
        "default":   "DEFAULT",
        "analyst":   "ANALYST",
        "reviewer":  "REVIEWER",
        "embedding": "EMBEDDING",
        "vision":    "VISION",
        "agent":     "AGENT",
    }
    if agent not in prefix_map:
        return False

    prefix = prefix_map[agent]
    for field, value in config.items():
        if not isinstance(value, str) or value.strip().lower() in _BAD_VALUES:
            continue
        attr = f"{prefix}_{field.upper()}"
        if hasattr(settings, attr):
            setattr(settings, attr, value.strip())

    return True


def get_effective_llm_config(agent: str) -> dict:
    """
    获取指定 Agent 的有效配置，空缺字段自动回退到 DEFAULT。
    agent: "analyst" | "reviewer" | "embedding" | "vision" | "agent"
    """
    prefix_map = {
        "analyst":   "ANALYST",
        "reviewer":  "REVIEWER",
        "embedding": "EMBEDDING",
        "vision":    "VISION",
        "agent":     "AGENT",   # v2 修复 #2.1
    }
    prefix = prefix_map.get(agent)
    if not prefix:
        return {}

    def field(name):
        specific = getattr(settings, f"{prefix}_{name.upper()}", "") or ""
        return specific if specific else getattr(settings, f"DEFAULT_{name.upper()}", "") or ""

    return {
        "api_key": field("api_key"),
        "base_url": field("base_url"),
        "model": field("model"),
    }


def get_agent_config() -> tuple[str, str, str]:
    """
    Agent 智能体配置回退链（修复 #2.1）：
        AGENT_* → ANALYST_* → DEFAULT_*
    返回 (api_key, base_url, model)
    """
    def field(name: str) -> str:
        # AGENT 优先
        v = getattr(settings, f"AGENT_{name.upper()}", "") or ""
        if v:
            return v
        # 回退到 ANALYST
        v = getattr(settings, f"ANALYST_{name.upper()}", "") or ""
        if v:
            return v
        # 回退到 DEFAULT
        return getattr(settings, f"DEFAULT_{name.upper()}", "") or ""

    return field("api_key"), field("base_url"), field("model")