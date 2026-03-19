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
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
    KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1").strip()
    KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k2.5")
    
    STATE_DB_PATH = os.getenv("STATE_DB_PATH", os.path.join(DATA_DIR, "radar_state.db"))
    CRAWLER_DB_PATH = os.getenv("CRAWLER_DB_PATH", os.path.join(BACKEND_DIR, "data", "sqlite_tables.db"))
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

settings = Settings()