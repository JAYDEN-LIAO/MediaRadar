# MediaRadar Public Opinion Monitoring System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.0-42b883.svg" alt="Vue">
  <img src="https://img.shields.io/badge/Qdrant-1.7+-46A0B6.svg" alt="Qdrant">
</p>

> 「 Not just a crawler — it's an industrial-grade **AI brain** for public opinion monitoring, featuring **multimodal vision**, **multi-agent collaboration**, **topic evolution tracking**, and **RAG knowledge base**. 」

An enterprise-grade public opinion monitoring system built with FastAPI + uni-app. Through deep integration of multiple large language models and a proprietary high-availability crawler architecture, it achieves full-network data collection, cross-modal evidence parsing, multi-AI cross-validation, topic aggregation, evolution tracking, and real-time alert pushing.

---

## Key Features

### 🔄 Multi-Agent Collaboration Pipeline

```
Crawler collects raw posts
     │
     ▼
┌─────────────────────────────────────────────┐
│ ① Screener (Initial Filtering)              │
│    Early Exit for irrelevant posts          │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ② Vision Agent (Image Evidence Extraction) │
│    Joint image-text judgment (conditional)  │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ③ Cluster (HDBSCAN + Semantic Clustering)   │
│    Topic aggregation + union-find safety net │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ④ Analyst (Risk Assessment)                 │
│    RAG context from topic evolution          │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ⑤ Reviewer (Cross-Validation)               │
│    Prevent single-model hallucinations      │
└─────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│ ⑥ Director (Alert Briefing)                 │
│    High-risk alert generation               │
└─────────────────────────────────────────────┘
     │
     ▼
Alert Push + Topic Aggregation Write + Async Qdrant Index
```

### 📊 Topic Aggregation & Evolution Tracking

Elevated from **post-level** to **topic-level** for more precise risk management:

| Capability | Description |
|------------|-------------|
| Semantic Clustering | HDBSCAN groups semantically similar posts into topic clusters |
| Smart Merging | Union-find safety net automatically merges highly similar topics |
| Evolution Tracking | Shows "risk evolution path" e.g. `2 → 3 → 4` |
| Evolution Signals | Identifies topics as escalating / stable / de-escalating |
| RAG Enhancement | Auto-links historical cases for Analyst |

### 👁️ Multimodal Vision Detective

Automatically reads local HD images, precisely capturing and parsing visual evidence such as "foreign objects, messiness, error screenshots" in images — solving the image-text separation problem.

### ⚖️ Cross-Source LLM Cross-Validation

```
Analyst (logical reasoning) ──┐
                               ├──► Dual-track review defense
Reviewer (deep review + report) ┘
```

### 📢 Multi-Channel Alert Push

Supports three push channels, independently configurable:

| Channel | Description |
|---------|-------------|
| WeCom (企业微信) | Webhook bot, Markdown format, color-coded risk levels |
| Feishu (飞书) | Interactive card messages, color distinguishes risk levels |
| Email | SMTP TLS, HTML + plain text dual format, auto-bundled summary |

Each channel is independently configured and can filter by risk level (1–5).

---

## Supported Platforms

<p float="left">
  <img src="https://img.shields.io/badge/-%E5%B0%8F%E7%BA%A2%E4%B9%A6-EA5A89?style=flat-square" alt="小红书">
  <img src="https://img.shields.io/badge/-%E5%BE%AE%E5%8D%9A-F0999D?style=flat-square" alt="微博">
  <img src="https://img.shields.io/badge/-%E6%8A%96%E9%9F%B3-25F4EE?style=flat-square" alt="抖音">
  <img src="https://img.shields.io/badge/-%E7%9F%A5%E4%B9%8E-0084FF?style=flat-square" alt="知乎">
  <img src="https://img.shields.io/badge/-B%E7%AB%99-FF9C02?style=flat-square" alt="B站">
  <img src="https://img.shields.io/badge/-%E8%B4%B0%E9%82%BA-BA1C26?style=flat-square" alt="贴吧">
</p>

---

## Architecture

### Dual-Layer RAG Knowledge Base

| Collection | Storage Unit | Purpose |
|------------|--------------|---------|
| `yq_history` | Single-post analysis results | Analyst historical case reference |
| `topic_evolution` | Topic cluster summary + evolution track | Analyst topic timeline context |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend Framework | FastAPI · SQLite · asyncio |
| AI Analysis | DeepSeek · Kimi/Moonshot · Qwen-VL-Max |
| Vector Engine | BGE-M3 · Qdrant (dual collections) |
| Clustering | HDBSCAN (adaptive density) + Union-Find |
| Dialogue Engine | DeepSeek + Function Calling + SSE |
| Frontend | uni-app (Vue 3) |
| Crawler | Playwright / Selenium |

### Model Configuration Mechanism

The system supports independent model configuration for each Agent role, with automatic fallback to the **default model** when not configured:

| Role | Purpose |
|------|---------|
| Default Model | Fallback for all agents |
| Analyst | Public opinion risk analysis |
| Reviewer | Cross-validation and judgment |
| Embedding Engine | Text vector clustering (BGE-M3) |
| Vision Engine | Image evidence parsing (Qwen-VL) |

---

## Quick Start

### Environment Setup

```bash
# Ensure Python 3.11+
python --version

# Initialize browser environment
playwright install
```

### Configure Environment Variables

```bash
# Create .env in project root
cat > .env << 'EOF'
# ======== Default Model (fallback for all agents) ========
DEFAULT_BASE_URL="https://api.deepseek.com/v1"
DEFAULT_API_KEY="sk-xxx"
DEFAULT_MODEL="deepseek-chat"

# ======== Analyst (optional, overrides default) ========
ANALYST_API_KEY=""
ANALYST_BASE_URL=""
ANALYST_MODEL=""

# ======== Reviewer (optional, overrides default) ========
REVIEWER_API_KEY=""
REVIEWER_BASE_URL=""
REVIEWER_MODEL=""

# ======== Embedding Engine (optional, overrides default) ========
EMBEDDING_API_KEY=""
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL=""

# ======== Vision Engine (optional, overrides default) ========
VISION_API_KEY=""
VISION_BASE_URL=""
VISION_MODEL=""

# ======== Qdrant Vector Database ========
QDRANT_HOST="127.0.0.1"
QDRANT_PORT="6333"
QDRANT_COLLECTION="yq_history"
TOPIC_COLLECTION="topic_evolution"

# ======== Push Channels (optional) ========
# WeCom Webhook
WECOM_WEBHOOK_URL=""
# Feishu Webhook
FEISHU_WEBHOOK_URL=""
# Email SMTP
SMTP_HOST=""
SMTP_PORT="587"
SMTP_USER=""
SMTP_PASSWORD=""
SMTP_FROM=""

# ======== Logging (optional) ========
LOG_LEVEL="INFO"
LOG_FORMAT="text"
LOG_TO_FILE="true"
LOG_TO_CONSOLE="true"
EOF
```

### Start Services

```bash
# 1. Start Qdrant
docker run -d --name mediaradar-qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest

# 2. Start backend
python backend/gateway/main.py
# Visit http://127.0.0.1:8000/docs for API docs

# 3. Initialize topic evolution knowledge base (one-time)
python scripts/rag/migrate_topic_evolution.py

# 4. Start frontend
# Use HBuilderX to open frontend/MiniApp directory and run
```

---

## API Endpoints

### Radar Operations

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/start_task` | POST | Trigger full-network scan (background) |
| `/api/radar_status` | GET | Get radar running status |
| `/api/settings` | GET / POST | Get/save system configuration |
| `/api/mcp/health` | GET | MCP Server health check |

### Push Channels

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/push/configs` | GET | Get all push configurations |
| `/api/push/config/{channel}` | GET | Get specific channel config |
| `/api/push/config/{channel}` | POST | Save push channel config |
| `/api/push/test` | POST | Test push channel connectivity |

### Model Configuration

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/llm/configs` | GET | Get all Agent model configurations |
| `/api/llm/config/{agent}` | POST | Update specific Agent model config |
| `/api/llm/test/{agent}` | POST | Test specific Agent model connectivity |

### Topic Aggregation

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/topic_list` | GET | Topic aggregation list |
| `/api/topic/{topic_id}` | GET | Topic detail (posts + evolution timeline) |
| `/api/topic/{topic_id}/process` | POST | Mark topic as processed |
| `/api/topic_evolution` | GET | Get full topic evolution timeline |
| `/api/topic_evolution/migrate_clusters` | POST | Batch migrate historical data |
| `/api/topic_stats` | GET | Topic evolution library statistics |

### Public Opinion & AI Assistant

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/api/yq_list` | GET | Public opinion list (latest 50) |
| `/api/agent/chat` | POST | AI assistant streaming chat (SSE + Function Calling) |

---

## Logging System

Logs are stored by module subdirectory, supporting `text` / `json` dual format:

```
logs/
├── radar/          # Radar service (pipeline / cluster / analysis / tracker...)
├── crawler/        # Crawler service
├── agent/          # AI assistant service
├── gateway/        # API gateway
├── audit/          # Audit logs (alerts, config changes)
└── error/          # Error summary
```

```python
from core.logger import get_logger
from core.context import set_task_context

logger = get_logger("radar.pipeline")

# Request-level context tracking
set_task_context(task_id="xxx", keyword="Li Ronghao", platform="WB")
```

---

## Project Structure

```
MediaRadar/
├── backend/
│   ├── core/                    # Global core
│   │   ├── config.py           # Configuration (Qdrant / LLM configs)
│   │   ├── database.py         # SQLite connection
│   │   ├── logger.py           # Log factory (text/json dual format)
│   │   ├── context.py          # Request context (task_id tracking)
│   │   └── audit.py            # Audit log
│   ├── gateway/
│   │   └── main.py             # FastAPI unified gateway (port 8000)
│   └── services/
│       ├── agent_service/       # AI opinion assistant
│       │   ├── agent_core.py   # Streaming dialogue engine + Function Calling
│       │   ├── tools.py        # Toolset
│       │   └── api.py
│       ├── radar_service/       # Core opinion analysis
│       │   ├── main.py         # Dispatcher main program
│       │   ├── pipeline.py     # Pipeline dispatcher
│       │   ├── llm_pipeline.py # LangGraph analysis subgraph
│       │   ├── embed_cluster.py # HDBSCAN clustering
│       │   ├── analysis_graph.py # LangGraph graph
│       │   ├── topic_tracker.py # Topic evolution tracking
│       │   ├── topic_aggregator.py # Topic aggregation
│       │   ├── vector_store.py  # Qdrant wrapper
│       │   ├── vision_agent.py # Visual evidence extraction
│       │   ├── llm_gateway.py  # LLM gateway
│       │   ├── db_manager.py   # SQLite CRUD
│       │   ├── schemas.py      # Data contracts
│       │   ├── prompt_templates.py
│       │   ├── notifier/       # Alert push (package)
│       │   │   ├── __init__.py
│       │   │   ├── base.py     # NotifierBase abstract class
│       │   │   ├── registry.py # Push dispatcher
│       │   │   ├── models.py  # Data models
│       │   │   ├── channel_email.py
│       │   │   ├── channel_wecom.py
│       │   │   └── channel_feishu.py
│       │   └── api.py
│       └── crawler_service/     # Crawler engine
├── frontend/
│   └── MiniApp/                 # uni-app (Vue 3)
│       └── src/
│           └── pages/
│               ├── index/        # Dashboard
│               ├── list/         # Opinion list / topic detail
│               ├── chat/         # AI assistant
│               ├── profile/      # Profile center
│               └── settings/      # Monitor settings / push settings / model settings
├── scripts/
│   └── rag/                     # Data migration scripts
├── plans/                       # Planning documents
└── .env
```

---

## Changelog

| Version | Content |
|---------|---------|
| v2.1 | Multi-channel alert push: WeCom / Feishu / Email, independent risk level config |
| v2.1 | Model settings page: default model fallback + per-agent independent config |
| v2.0 | Logging system refactored, stored by module, text/json dual format |
| v2.0 | Topic aggregation, upgraded from post-level to topic cluster level |
| v2.0 | Topic evolution tracking, RAG enhancement + risk evolution path display |
| v1.0 | Pipeline 5-stage dispatcher, LangGraph Multi-Agent architecture |
| v1.0 | Vision Agent, multimodal visual evidence extraction |
