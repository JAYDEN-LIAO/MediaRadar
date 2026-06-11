# MediaRadar

Multi-platform social media monitoring, search engine, and AI-powered opinion analysis system.

## Overview

MediaRadar is a full-stack platform for crawling, searching, and analyzing public opinion across Chinese social media platforms. It supports real-time search, scheduled monitoring, AI-powered risk assessment, and multi-channel alerting.

### Key Features

- **Media Search Engine** — On-demand crawling across 7 platforms (Weibo, Xiaohongshu, Bilibili, Douyin, Kuaishou, Tieba, Zhihu)
- **Opinion Monitoring** — Scheduled crawling + AI analysis with risk level assessment
- **Multi-Agent AI Analysis** — LangGraph pipeline: analyst → reviewer → director
- **Multi-channel Alerts** — Email, WeCom, Feishu push notifications + RSS subscription
- **Subscription Engine** — Per-user subscriptions with type/polarity/sensitivity/push_mode control
- **Per-User Isolation** — Each user's data, config, and alerts are fully isolated
- **AI Chat Agent** — 26 function-calling tools across 7 groups for natural language system control
- **Multi-user & Auth** — Email/password registration + Google OAuth + JWT + API Key dual auth
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
├── gateway/main.py           # FastAPI entry point (port 8008)
├── core/                     # Core components
│   ├── config.py             # Settings (3-tier fallback: DEFAULT→LLM→hardcoded)
│   ├── auth*.py              # JWT, user DB, auth deps, login lockout
│   ├── subscription_db.py    # Subscription CRUD (per-owner)
│   ├── quota_db.py           # Per-user quota management
│   ├── model_config_db.py    # Per-agent model config with fallback
│   ├── agent_memory_db.py    # Session memory persistence
│   ├── circuit_breaker.py    # LLM circuit breaker
│   ├── logger.py             # Structured logging (JSON/colored)
│   ├── metrics.py            # Prometheus metrics
│   ├── sanitize.py           # HTML sanitization
│   ├── security_middleware.py # Security headers & body size limit
│   └── rate_limiter.py       # Rate limiter (skips unauthenticated non-auth paths)
├── services/
│   ├── radar_service/        # Opinion monitoring core
│   │   ├── pipeline.py       # Pipeline orchestrator (Screener→Vision→Cluster→Alert)
│   │   ├── llm_gateway.py    # LangGraph analysis sub-graph (analyst→reviewer→director)
│   │   ├── db_manager.py     # SQLite operations
│   │   ├── scheduler.py      # APScheduler (per-user scan + daily summary)
│   │   ├── push_generator.py # HTML email templates
│   │   └── notifier/         # Alert pushes (email/wecom/feishu/rss)
│   ├── agent_service/        # AI chat agent (26 tools, SSE streaming)
│   │   ├── agent_core.py     # Chat engine + function calling
│   │   ├── tools/            # Tool modules by group (subscription/scan/query/push/model/system)
│   │   └── memory/           # Agent memory (jieba, TTL cache)
│   ├── auth_service/         # Multi-user auth & OAuth
│   │   └── oauth_providers/  # Google OAuth
│   ├── subscription_service/ # Subscription/quota/admin API
│   ├── search_lib/           # Search library
│   └── crawler_service/      # Platform crawlers (independent, port 8080)
frontend/
├── web/                      # Next.js dashboard (port 3003)
└── MiniApp/                  # uni-app mobile
scripts/                      # P1-P3 verification test scripts
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

### Auth (`auth_service`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Email/password registration |
| `/api/auth/login` | POST | Login (returns JWT) |
| `/api/auth/refresh` | POST | Token refresh |
| `/api/auth/me` | GET | Current user info |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/change-password` | POST | Change password |
| `/api/auth/set-password` | POST | Set password (OAuth users) |
| `/api/auth/oauth/{provider}/login` | GET | OAuth login (WeChat/Google) |
| `/api/auth/oauth/{provider}/callback` | GET | OAuth callback |
| `/api/admin/users` | GET | User list (admin) |
| `/api/admin/users/{id}` | DELETE | Delete user (admin) |
| `/api/admin/users/{id}/reactivate` | POST | Reactivate user (admin) |

### Radar (`radar_service`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/radar_status` | GET | Radar running status |
| `/api/start_task` | POST | Trigger full scan |
| `/api/yq_list` | GET | Opinion list |
| `/api/settings` | GET/POST | System config (keywords/platforms) |
| `/api/circuit/states` | GET | Circuit breaker status |
| `/api/mcp/health` | GET | MCP health |
| `/api/scheduler/start` | POST | Start APScheduler |
| `/api/scheduler/stop` | POST | Stop scheduler |
| `/api/scheduler/status` | GET | Scheduler status |
| `/api/topic_list` | GET | Topic list |
| `/api/topic/{id}` | GET | Topic detail |
| `/api/topic/{id}/process` | POST | Process topic |
| `/api/topic_evolution` | GET | Topic evolution |
| `/api/topic_evolution/migrate_clusters` | POST | Migrate clusters |
| `/api/topic_stats` | GET | Topic statistics |
| `/api/volume_stats` | GET | Volume statistics |
| `/api/today_summary` | GET | Today's AI summary |
| `/rss/{token}.xml` | GET | RSS feed |

### Push Config
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/push/configs` | GET | All push configs |
| `/api/push/config/{channel}` | GET/POST | Get/save channel config |
| `/api/push/test` | POST | Test push channel |

### Model Config
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/llm/configs` | GET | All model configs (with fallback) |
| `/api/llm/config/{agent}` | POST | Update agent model config |
| `/api/llm/test/{agent}` | POST | Test agent connectivity |

### AI Agent (`agent_service`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agent/chat` | POST | AI chat (SSE stream) |
| `/api/agent/memory` | GET | Session list |
| `/api/agent/memory/{id}` | GET/DELETE | Session detail/delete |

### Subscription (`subscription_service`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/subscriptions` | GET/POST | List/create subscriptions |
| `/api/subscriptions/{id}` | GET/DELETE | Subscription detail/delete |
| `/api/model-configs` | GET | Model configs |
| `/api/model-configs/{role}` | PUT/DELETE | Update/delete model config |
| `/api/quota` | GET | Quota info |
| `/api/admin/stats` | GET | Admin statistics |
| `/api/admin/users/{id}` | GET | User detail (admin) |
| `/api/admin/users/{id}/quota` | GET/PUT | User quota (admin) |
| `/api/admin/users/{id}/deactivate` | POST | Deactivate user (admin) |
| `/api/admin/users/{id}/role` | POST | Change role (admin) |

### Gateway
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics` | GET | Prometheus metrics |
| `/health` | GET | Health check (includes scheduler status) |

## AI Agent

The AI assistant has 26 function-calling tools across 7 groups:

| Group | Tools | Purpose |
|-------|-------|---------|
| A | 5 | Subscription management + intent parsing |
| B | 6 | Scan/schedule control |
| C | 3 | Data query + web search |
| D | 4 | Push channel management |
| E | 3 | Model configuration |
| F | — | Reserved for system tools |
| G | 1 | System status |

The agent uses a streaming SSE chat endpoint and maintains per-session memory with jieba keyword extraction and TTL-based cache cleanup.

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
