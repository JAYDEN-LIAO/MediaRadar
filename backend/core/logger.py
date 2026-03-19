# backend/core/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from core.config import settings

if not os.path.exists(settings.LOG_DIR):
    os.makedirs(settings.LOG_DIR)

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
log_file = os.path.join(settings.LOG_DIR, 'media_radar.log')

file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger('MediaRadar')
logger.setLevel(logging.INFO)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)