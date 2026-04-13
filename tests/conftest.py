"""Pytest fixtures for MediaRadar tests"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# 确保 backend/ 目录在 path 中（services 和 core 模块在其下）
_backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, os.path.normpath(_backend_dir))

# 同时保留项目根目录（用于 core 模块）
_root_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.normpath(_root_dir))

@pytest.fixture
def mock_settings():
    """Mock settings object"""
    with patch('core.config.settings') as mock:
        mock.ANALYST_API_KEY = "test-key"
        mock.ANALYST_BASE_URL = "https://api.deepseek.com/v1"
        mock.ANALYST_MODEL = "deepseek-chat"
        mock.REVIEWER_API_KEY = "test-key"
        mock.REVIEWER_BASE_URL = "https://api.moonshot.cn/v1"
        mock.REVIEWER_MODEL = "moonshot-v1-8k"
        mock.EMBEDDING_API_KEY = "test-key"
        mock.EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
        mock.EMBEDDING_MODEL = "BAAI/bge-m3"
        mock.QDRANT_HOST = "127.0.0.1"
        mock.QDRANT_PORT = 6333
        yield mock

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response"""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = '{"is_relevant": true, "generated_title": "测试标题"}'
    return response
