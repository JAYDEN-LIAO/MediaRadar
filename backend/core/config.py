# backend/core/config.py
import os
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

DATA_DIR = os.path.join(BACKEND_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

ENV_PATH = os.path.join(BACKEND_DIR, "services", "radar_service", ".env")
load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    # LLM 配置
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    

    STATE_DB_PATH = os.getenv("STATE_DB_PATH", os.path.join(PROJECT_ROOT, "radar_state.db"))
    CRAWLER_DB_PATH = os.getenv("CRAWLER_DB_PATH", os.path.join(BACKEND_DIR, "services", "crawler_service", "database", "sqlite_tables.db"))
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

settings = Settings()