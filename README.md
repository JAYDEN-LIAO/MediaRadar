# MediaRadar

Multi-platform social media monitoring, search engine, and AI-powered opinion analysis system.

## Overview

MediaRadar is a full-stack platform for crawling, searching, and analyzing public opinion across Chinese social media platforms. It supports real-time search, scheduled monitoring, AI-powered risk assessment, and multi-channel alerting.

### Key Features

- **Media Search Engine** — On-demand crawling across 7 platforms (Weibo, Xiaohongshu, Bilibili, Douyin, Kuaishou, Tieba, Zhihu)
- **Opinion Monitoring** — Scheduled crawling + AI analysis with risk level assessment
- **Multi-Agent AI Analysis** — LangGraph pipeline: analyst → reviewer → director
- **Multi-channel Alerts** — Email, WeCom, Feishu push notifications
- **Multi-user & Auth** — Email/password registration + Google OAuth + JWT
- **Web Dashboard** — Next.js 15 + Tailwind CSS + shadcn/ui
- **WeChat Mini Program** — uni-app mobile client
- **Prometheus Metrics** — LLM calls, pipeline duration, agent metrics

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLite |
| AI/LLM | LangGraph, DeepSeek, Kimi, Qwen-VL, BGE-M3 |
| Crawler | Playwright, httpx |
| Frontend (Web) | Next.js 15, Tailwind CSS, shadcn/ui, Framer Motion |
| Frontend (Mini) | uni-app (Vue 3) |
| Auth | JWT (HS256), bcrypt, Google OAuth 2.0 |
| Scheduler | APScheduler |
| Monitoring | Prometheus |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+

### Backend

```bash
cd backend
pip install -r ../requirements.txt
cp ../.env.example ../.env   # Edit with your API keys
python gateway/main.py       # API at http://localhost:8008
```

### Web Frontend

```bash
cd frontend/web
npm install
npm run dev                  # UI at http://localhost:3003
```

### Mini Program

```bash
cd frontend/MiniApp
npm install
# Open with HBuilder X or Weixin DevTools
```

## Project Structure

```
backend/
├── gateway/main.py           # FastAPI entry point
├── core/                     # Core components
│   ├── config.py             # Settings (env vars)
│   ├── auth*.py              # JWT, user DB, auth deps
│   ├── circuit_breaker.py    # LLM circuit breaker
│   ├── logger.py             # Logging (JSON/colored)
│   ├── metrics.py            # Prometheus metrics
│   ├── sanitize.py           # HTML sanitization
│   ├── security_middleware.py # Security headers & rate limiting
│   └── rate_limiter.py       # Rate limiter
├── services/
│   ├── radar_service/        # Opinion monitoring core
│   │   ├── pipeline.py       # Pipeline orchestrator
│   │   ├── analysis_graph.py # LangGraph analysis
│   │   ├── db_manager.py     # SQLite operations
│   │   ├── scheduler.py      # APScheduler
│   │   ├── push_generator.py # HTML email templates
│   │   └── notifier/         # Alert pushes
│   ├── agent_service/        # AI chat agent
│   │   ├── agent_core.py     # Chat engine + function calling
│   │   ├── tools.py          # Status/crawl/alert tools
│   │   └── memory/           # Agent memory (jieba, TTL)
│   ├── auth_service/         # Multi-user auth & OAuth
│   │   └── oauth_providers/  # Google OAuth
│   └── crawler_service/      # Platform crawlers (independent)
frontend/
├── web/                      # Next.js dashboard
└── MiniApp/                  # uni-app mobile
tests/
├── unit/                     # Phase 1-7 + security tests
└── api_e2e_test.py           # API end-to-end tests
```

## Core Architecture

```
Search / Cron Trigger
        │
        ▼
  Pipeline Orchestrator
  ① Screener → ② Vision → ③ Cluster
                                  │
                                  ▼
                       LangGraph Analysis
                       Analyst → Reviewer → Director
                                  │
                                  ▼
                         Alert / Push Notification
```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Email/password registration |
| `/api/auth/login` | POST | Email/password login |
| `/api/auth/oauth/google/login` | GET | Google OAuth |
| `/api/auth/me` | GET | Current user info |
| `/api/radar_status` | GET | Radar status |
| `/api/today_summary` | GET | Today's AI summary |
| `/api/volume_stats` | GET | Volume stats with keyword breakdown |
| `/api/topic_list` | GET | Paginated topic list |
| `/api/agent/chat` | POST | AI agent chat (SSE stream) |
| `/api/circuit/states` | GET | Circuit breaker status |
| `/metrics` | GET | Prometheus metrics |

## Configuration

Key environment variables (`.env`):

```env
# LLM API Keys
DEFAULT_API_KEY=sk-...
ANALYST_API_KEY=sk-...

# Auth
JWT_SECRET=your-secret-32bytes-min
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Deployment
ENV=dev|prod
ALLOWED_ORIGINS=https://your-domain.com
```

See `.env.production.example` for full reference.

## License

MIT
