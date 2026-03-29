# MediaRadar MCP Server

> 舆情监控系统的 MCP (Model Context Protocol) Server 实现，将 MediaRadar 的核心能力封装为 AI Agent 可直接调用的 Tools 和 Resources。

## 功能概览

```
用户: "帮我查一下华为最近的舆情"
        ↓
Claude Code (MCP Client)
        ↓ (stdio)
MediaRadar MCP Server
        ↓
  ├── Tools (14个)
  │   ├── crawl_platform / crawl_all_platforms
  │   ├── screener_posts / vision_analyze / cluster_posts
  │   ├── analyze_cluster / analyze_cluster_stream / run_full_pipeline
  │   ├── get_radar_status / get_recent_alerts / send_alert
  │   └── get_keywords / update_keywords
  │
  └── Resources (5个)
      ├── radar://status
      ├── radar://keywords
      ├── radar://platforms
      ├── radar://alerts
      └── radar://yq-list
```

## 快速开始

### 1. 安装依赖

```bash
cd backend/services/mcp_service
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入各 API Key
```

**所需环境变量**（与 radar_service 共用）：
```env
ANALYST_API_KEY=sk-xxx        # DeepSeek API Key
REVIEWER_API_KEY=sk-xxx       # Kimi/Moonshot API Key
EMBEDDING_API_KEY=sk-xxx      # 硅基流动 API Key
VISION_API_KEY=sk-xxx          # 阿里云 API Key
```

### 3. 本地 Claude Code 集成

项目根目录已包含 `.mcp.json`，Claude Code 启动时会自动读取。

或手动配置 `~/.claude/settings.json`：
```json
{
  "mcpServers": {
    "mediaradar": {
      "command": "python",
      "args": [
        "D:/jayden/develop/work/mediaradar/backend/services/mcp_service/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "D:/jayden/develop/work/mediaradar/backend"
      }
    }
  }
}
```

### 4. 启动 MCP Server

```bash
# stdio 模式（Claude Code 集成用）
python backend/services/mcp_service/mcp_server.py

# HTTP 模式（云端部署 / 多客户端）
python backend/services/mcp_service/mcp_server.py --transport http --host 0.0.0.0 --port 8001
```

## Tools 完整列表

### 爬虫工具

| Tool | 描述 | 参数 |
|------|------|------|
| `crawl_platform` | 抓取单个平台数据 | `platform` (必填), `keyword`, `headless` |
| `crawl_all_platforms` | 全平台抓取 | `keyword`, `headless` |
| `get_crawler_status` | 获取爬虫运行状态 | 无 |

### Pipeline 工具

| Tool | 描述 | 参数 |
|------|------|------|
| `screener_posts` | 文本初筛帖子 | `posts`, `keywords`, `keyword_levels` |
| `vision_analyze` | 视觉图片分析 | `image_url`, `post_text`, `platform` |
| `cluster_posts` | 向量聚类帖子 | `posts`, `keyword` |
| `analyze_cluster` | LangGraph 全链路分析 | `posts`, `keyword`, `sensitivity` |
| `analyze_cluster_stream` | LangGraph 全链路分析（流式） | `posts`, `keyword`, `sensitivity` |
| `run_full_pipeline` | 端到端完整分析管线 | `keyword`, `platform`, `sensitivity` |

### 预警与状态工具

| Tool | 描述 | 参数 |
|------|------|------|
| `get_radar_status` | 获取雷达系统运行状态 | 无 |
| `get_recent_alerts` | 查询高危预警历史 | `limit`, `min_level` |
| `send_alert` | 手动发送预警 | `keyword`, `platform`, `risk_level`, `core_issue`, `report`, `urls` |

### 配置管理工具

| Tool | 描述 | 参数 |
|------|------|------|
| `get_keywords` | 获取当前监控关键词配置 | 无 |
| `update_keywords` | 更新监控关键词配置 | `keywords`, `keyword_levels` |

## Resources 完整列表

| Resource URI | 描述 |
|-------------|------|
| `radar://status` | 雷达系统运行状态 |
| `radar://keywords` | 当前监控关键词配置 |
| `radar://platforms` | 支持的平台列表 |
| `radar://alerts` | 预警历史记录 |
| `radar://yq-list` | 舆情列表 |

## 平台枚举

| ID | 名称 |
|-----|------|
| `wb` | 微博 |
| `xhs` | 小红书 |
| `bili` | 哔哩哔哩 |
| `zhihu` | 知乎 |
| `dy` | 抖音 |
| `ks` | 快手 |
| `tieba` | 百度贴吧 |

## 敏感度枚举

| 值 | 描述 |
|-----|------|
| `aggressive` | 激进：轻微负面也上报 |
| `balanced` | 平衡：标准公关危机判定（默认） |
| `conservative` | 保守：仅重大危机上报 |

## 典型对话场景

### 场景 1：查询舆情
```
用户：帮我看看华为最近有什么舆情
AI Tool：crawl_platform(platform="wb", keyword="华为")
AI Tool：screener_posts(posts=[...], keywords=["华为"])
AI Tool：cluster_posts(posts=[...], keyword="华为")
AI Tool：analyze_cluster(posts=[...], keyword="华为", sensitivity="balanced")
```

### 场景 2：全网扫描
```
用户：全网扫描一下小米
AI Tool：run_full_pipeline(keyword="小米", sensitivity="balanced")
```

### 场景 3：查询预警
```
用户：最近有哪些高危舆情
AI Tool：get_recent_alerts(limit=5, min_level=3)
```

### 场景 4：更新配置
```
用户：把监控关键词换成苹果和三星
AI Tool：update_keywords(keywords=["苹果", "三星"], keyword_levels={"苹果": "balanced", "三星": "balanced"})
```

## 流式输出

`analyze_cluster_stream` 和 `run_full_pipeline` 支持 SSE 流式输出，事件类型：

```
event: analysis_progress
data: {"node": "analyst", "status": "completed", "risk_level": 3}

event: analysis_progress
data: {"node": "reviewer", "status": "completed", "risk_level": 4}

event: final_result
data: {"result": {...}, "topic_name": "华为被制裁"}

event: completed
data: {"total_results": 5}
```

## 项目结构

```
backend/services/mcp_service/
├── mcp_server.py          # FastMCP Server 入口
├── config.json             # 服务配置
├── .env.example           # 环境变量模板
├── adapter/               # 与原系统的适配层
│   ├── radar_adapter.py   # radar_service 适配
│   └── crawler_adapter.py # crawler_service 适配
├── tools/                 # Tools 实现
│   ├── crawl_tools.py
│   ├── pipeline_tools.py
│   ├── alert_tools.py
│   └── config_tools.py
├── resources/             # Resources 实现
│   └── radar_resources.py
└── schemas/               # 类型定义
    ├── mcp_types.py
    └── stream_events.py
```

## 云端部署

切换为 HTTP 模式：

```bash
python mcp_server.py --transport http --host 0.0.0.0 --port 8001
```

HTTP 模式下，MCP Server 作为 HTTP 服务运行，支持：
- `GET /mcp` — MCP 协议端点
- `POST /mcp` — 接收 JSON-RPC 请求
- SSE 流式响应

## 与原项目的关系

- MCP Server 独立进程，不修改原项目代码
- 原项目（radar_service / agent_service）不受 MCP 影响
- MCP Server 通过 Adapter 层调用原系统功能
