# Agent 改造扩展方案 (AGENT_REDESIGN)

> 制定时间：2026-06-10（v2 定位：媒体信息订阅平台）
> 配套文档：根目录 `update.md`（v2 战略总览）
> 适用范围：MediaRadar v2 中 Agent 模块的完整改造与扩展
> 状态：方案完整，待开发

---

## 1. 目标与设计原则

### 1.1 目标

把当前只挂 3 个工具的 Agent，改造为承载 **几乎所有订阅/推送/搜索操作** 的「媒体信息管家」，作为 v2 产品的唯一主入口。

### 1.2 设计原则

| 原则 | 含义 |
|------|------|
| **对话即操作** | 用户不需要离开 Chat 就能完成所有日常工作 |
| **单 Agent 多 tool** | 不用 multi-agent router，靠 prompt 分组让 LLM 自行选择 |
| **工具命名规范** | 动词_对象 + 一致性，降低 LLM 选错概率 |
| **结果可视化** | 每个工具返回携带 UI hint，前端渲染对应卡片 |
| **流式优先** | 长耗时工具（搜索、扫描）支持流式增量推送 |
| **多用户隔离** | 所有工具带 `owner_id`，数据严格按用户隔离 |
| **无破坏性确认** | 信任 LLM，靠卡片"撤销"按钮兜底（决策已锁定） |
| **类型猜测 + 用户确认** | `parse_intent` 解析后必须经 `confirm_intent` 卡片确认才落库 |

### 1.3 不改的部分

`agent_core.py` 已有的 **TokenBudgetManager / AgentMemoryManager / ReflectionEngine / DiagnosisEngine / 直调-MCP 双适配** 全部保留，只在外围扩展。

---

## 2. 工具集总览（26 个工具）

| 组 | 名称 | 工具数 | 职责 |
|----|------|------|------|
| **A** | **订阅管理 + 意图解析** | **5** | 订阅增删改查、自然语言订阅（含类型猜测 + 用户确认） |
| B | 扫描 / 调度 | 5 | 触发扫描、查进度、改频率、暂停/恢复 |
| C | 数据查询 | 3 | 检索预警/动态、查话题详情、查统计 |
| D | 推送通道 | 4 | 列出/启用/测试/配置 通道（含 RSS） |
| E | 模型管理 | 3 | 切换/测试 5 个 Agent 角色模型 |
| **F** | **全网搜索** | **3** | 流式搜索、查搜索历史、清空缓存 |
| G | 系统状态 | 3 | 系统总览、最近活动、健康检查 |

★ 全部 v2 一次性实现，按 owner 隔离。

---

## 3. 工具命名规范

| 类型 | 前缀 | 示例 |
|------|------|------|
| 查询单个 | `get_` | `get_scan_status` / `get_topic_detail` |
| 查询列表 | `list_` | `list_subscriptions` / `list_push_channels` |
| 复杂检索 | `search_` | `search_alerts` / `web_search` |
| 新增 | `add_` | `add_subscription` |
| 修改 | `update_` | `update_subscription` / `update_channel_config` |
| 删除 | `remove_` | `remove_subscription` |
| 启停切换 | `toggle_` / `pause_` / `resume_` | `toggle_channel` / `pause_scheduler` |
| 一次性动作 | `trigger_` / `test_` / `parse_` | `trigger_scan` / `test_channel` / `parse_intent` |

★ 重要重命名：`keyword` → `subscription`（从舆情关键词翻转为信息订阅）。原 `add_keyword` / `update_keyword` / `remove_keyword` / `list_keywords` 全部改名为 `add_subscription` / `update_subscription` / `remove_subscription` / `list_subscriptions`。

---

## 4. 工具详细设计

### 4.A 订阅管理 + 意图解析

#### A1. `list_subscriptions`
```yaml
description: 列出当前用户的所有订阅及其配置（类型、极性、扫描频率、推送模式）。无参数。
parameters: {}
returns:
  data: list[SubscriptionItem]
  ui: {type: subscription_list}
owner_scope: 当前用户
后端映射: SELECT * FROM subscription WHERE owner_id = current_user
```

#### A2. `add_subscription`
```yaml
description: |
  新增一个订阅。通常由 parse_intent → 用户确认 confirm_intent 卡片后调用。
  不会做"是否已存在"校验，由前端在 confirm_intent 卡片中提示用户。
parameters:
  name: {type: string, required: true}
  type: {type: enum[person,brand,event,industry,keyword], required: true}
  polarity: {type: enum[negative,positive,neutral,all], default: all}
  sensitivity: {type: enum[conservative,balanced,aggressive], default: balanced}
  frequency_min: {type: integer, default: 60, range: [5, 1440]}
  platforms: {type: list[string], default: []}
  push_mode: {type: enum[every,important,silent,off], default: important}
  show_risk_alert: {type: boolean, default: false, desc: 是否在动态流中夹带预警（默认 false 隐藏）}
returns:
  data: SubscriptionItem
  ui: {type: subscription_card, data: {...}}   # 含"编辑""移除"按钮
owner_scope: current_user
后端映射: INSERT INTO subscription (..., owner_id=current_user)
```

#### A3. `update_subscription`
```yaml
description: 修改已有订阅的任一属性。
parameters:
  subscription_id: {type: string, required: true}    # ⚠️ 用 id 而非 name，避免重名
  ... 其他字段同 add_subscription，均 optional
returns:
  data: {old: SubscriptionItem, new: SubscriptionItem}
  ui: {type: subscription_card, before: {...}, after: {...}}
owner_scope: current_user
```

#### A4. `remove_subscription`
```yaml
description: 删除一个订阅。
parameters:
  subscription_id: {type: string, required: true}
returns:
  data: {subscription_id, removed_at}
  ui: {type: subscription_card, deleted: true}  # 灰色 + "撤销"按钮
owner_scope: current_user
```

#### A5. `parse_intent`（自然语言订阅入口）
```yaml
description: |
  解析用户的自然语言订阅意图。
  当用户描述"我想关注 XX"、"帮我盯一下 XX" 时**优先**调用。
  调用后前端渲染 confirm_intent 卡片，等用户点确认才能继续 add_subscription。
parameters:
  utterance: {type: string, required: true}
returns:
  data: SubscriptionIntent
  ui: {type: intent_preview, data: {...}}    # 渲染 confirm 卡片
  next_action: confirm_intent                 # ⚠️ 中间步骤，提示 Agent 不要自动 add
owner_scope: current_user
后端实现: 新增 LLM 调用，prompt 强制 JSON 输出
```

**SubscriptionIntent Schema:**
```python
class SubscriptionIntent(BaseModel):
    name: str
    type: Literal["person","brand","event","industry","keyword"]
    type_confidence: float                # 0-1，卡片展示"猜测置信度"
    polarity: Literal["negative","positive","neutral","all"]
    sensitivity: Literal["conservative","balanced","aggressive"]
    push_mode: Literal["every","important","silent","off"]
    scene: str                            # "明星动态" / "品牌动态" / "产品测评" / "热点跟进"
    suggested_platforms: list[str] = []
    suggested_frequency_min: int = 60
    raw_input: str                        # 原始输入存档
```

**`confirm_intent` 卡片**（不单独作为一个工具，而是 parse_intent 渲染的中间 UI）：

```
┌── 📋 订阅预览 ─────────────┐
│  小米 SU7                  │
│  类型：品牌/产品（90% 确信）│
│  极性：中性                │
│  推送：重要才推（Agent 决定）│
│  频率：每 60 分钟          │
│  平台：全平台              │
│                            │
│  [✓ 确认订阅]   [修改]     │
└────────────────────────────┘
```

用户点确认 → 触发 `add_subscription`。LLM 不会"自作主张"落库。

---

### 4.B 扫描 / 调度控制

#### B1. `trigger_scan`
```yaml
description: 立即触发一次扫描。
parameters:
  mode: {type: enum[full,trending,fan_track,quick_search], default: trending}
  subscription_ids: {type: list[string], optional, desc: 只扫指定订阅；不填=扫当前用户全部}
  platforms: {type: list[string], optional}
returns:
  data: {task_id, started_at, estimated_duration_sec}
  ui: {type: scan_progress, data: {...}, streamable: true}
owner_scope: current_user
后端映射: 改造 api_start_task，支持 mode + 订阅子集
```

#### B2. `get_scan_status`
```yaml
description: 查询当前用户最近一次扫描的状态。
parameters: {}
returns:
  data: {is_running, status_text, last_run_time, last_new_topic_count, progress_pct}
  ui: {type: scan_status}
owner_scope: current_user
```

#### B3. `set_scan_interval`
```yaml
description: 修改当前用户的全局扫描频率。
parameters: {interval_min: integer, required, range: [5, 1440]}
returns: {data: {old, new, next_run_at}, ui: {type: scheduler_info}}
owner_scope: current_user
后端映射: scheduler API（per-user 配置）
```

#### B4. `pause_scheduler` / `resume_scheduler`
```yaml
description:
  pause: 暂停当前用户的定时扫描。
  resume: 恢复当前用户的定时扫描。
parameters: {}
returns: {data: {active, next_run_at}, ui: {type: scheduler_info}}
owner_scope: current_user
```

#### B5. `get_next_run_time`
```yaml
description: 查询当前用户下次扫描时间。
returns: {data: {next_run_at, interval_min, active}, ui: {type: scheduler_info}}
owner_scope: current_user
```

★ 调度器从全局单例改为 per-user 调度，但底层抓取任务按关键词合并（同关键词只跑一次）。

---

### 4.C 数据查询

#### C1. `search_alerts`
```yaml
description: |
  按多维度检索历史预警 / 动态。当用户说"最近小米有什么"、"上周的高危预警"时调用。
  返回两类内容：动态（话题级） + 预警（仅当用户开了预警模式时存在）。
parameters:
  keyword: {optional}
  platform: {enum[weibo,xhs,douyin,bilibili,zhihu,tieba,kuaishou], optional}
  risk_level_min: {integer, default: 1, range: [1,5]}
  type: {enum[dynamic,alert,all], default: all}    # ⚠️ v2 新增 type 字段
  start_time: {ISO8601, optional}
  end_time: {ISO8601, optional}
  limit: {integer, default: 10, range: [1, 50]}
returns:
  data: list[ItemUnion]  # 可能是 DynamicItem 或 AlertItem
  ui: {type: alert_list, data: [...]}
owner_scope: current_user
```

#### C2. `get_topic_detail`
```yaml
description: 查询某话题的完整详情（摘要 + 所有相关帖子 + 演化时间线 + Agent 总结）。
parameters:
  topic_id: {string, required}
returns: {data: TopicDetail, ui: {type: topic_card}}
owner_scope: current_user
```

#### C3. `get_subscription_stats`
```yaml
description: 查询某订阅的统计（话题数、热度趋势、平台分布、推送命中率、Agent 压住率）。
parameters:
  subscription_id: {string, required}
  days: {integer, default: 7, range: [1, 30]}
returns:
  data: {topic_count, trend_data, platform_dist, push_stats}
  ui: {type: stats_chart}     # Recharts 折线 + 饼图
owner_scope: current_user
```

---

### 4.D 推送通道

#### D1. `list_push_channels`
```yaml
description: 列出当前用户的所有推送通道及状态（邮箱/企微/飞书/RSS）。
returns: {data: list[ChannelInfo], ui: {type: channel_list}}
owner_scope: current_user
```

#### D2. `toggle_channel`
```yaml
parameters:
  channel: enum[email,wecom,feishu,rss]    # ⚠️ 新增 rss
  enabled: bool
returns: {data: ChannelInfo, ui: {type: channel_card}}
owner_scope: current_user
```

#### D3. `test_channel`
```yaml
description: 向指定通道发一条测试消息。
parameters:
  channel: enum[email,wecom,feishu,rss]
  message: {string, optional, default: "MediaRadar 测试消息"}
returns: {data: {success, latency_ms, error}, ui: {type: test_result}}
owner_scope: current_user
```

#### D4. `update_channel_config`
```yaml
parameters:
  channel: enum
  config: object   # email: {smtp_host, port, user, pwd, to}; wecom: {webhook}; feishu: {webhook}; rss: {access_token}
returns: {data: ChannelInfo, ui: {type: channel_card}}
owner_scope: current_user
```

★ RSS 通道：每用户生成 `/rss/{user_token}.xml` 端点，可被 Feedly / Inoreader / Reeder 订阅。

---

### 4.E 模型管理

#### E1. `list_models`
```yaml
description: 列出当前用户配置的 5 个 Agent 角色模型（含系统默认回退信息）。
returns: {data: list[ModelConfig], ui: {type: model_list}}
owner_scope: current_user
```

#### E2. `switch_model`
```yaml
parameters:
  agent_role: enum[DEFAULT,ANALYST,REVIEWER,EMBEDDING,VISION]
  provider: string     # deepseek / kimi / qwen / openai / custom
  model: string
  api_key: {optional, desc: 不填则复用现有用户配置}
returns: {data: ModelConfig, ui: {type: model_card}}
owner_scope: current_user
```

#### E3. `test_model`
```yaml
parameters: {agent_role: enum}
returns: {data: {success, latency_ms, sample_response, error}, ui: {type: test_result}}
owner_scope: current_user
```

★ 用户的 5 个 Agent 角色模型独立配置，未配则回退到 admin 设的系统默认。

---

### 4.F 全网搜索

#### F1. `web_search` ⭐ 流式工具
```yaml
description: |
  跨平台全网搜索（实时拉取，结果不入库）。
  与 search_alerts（查历史）不同，本工具是即时爬虫。
parameters:
  query: {string, required}
  platforms: {list[string], optional, desc: 不填=全平台}
  max_per_platform: {integer, default: 5, range: [1, 20]}
  time_range: {enum[1d,7d,30d,all], default: 7d}
returns:
  streamable: true
  partials: list[SearchResultItem]   # 每条增量推送
  final: {total, by_platform, query_summary}
  ui:
    type: search_stream
    progress_card: search_progress
    result_card: search_result_item
owner_scope: current_user（仅影响搜索历史缓存）
后端实现: backend/services/search_service/ 模块（Pipeline mode=quick_search）
```

**SearchResultItem Schema:**
```python
class SearchResultItem(BaseModel):
    title: str
    snippet: str          # LLM 一句话摘要
    url: str
    platform: str
    publish_time: str
    relevance: float
    image_url: str = ""
```

#### F2. `list_search_history`
```yaml
description: 列出当前用户**当前会话**的搜索历史。
parameters: {}
returns: {data: list[{query, timestamp, result_count}], ui: {type: search_history_list}}
后端实现: agent_service 内存 dict，key=(user_id, session_id)
```

#### F3. `clear_search_cache`
```yaml
description: 清空当前会话的搜索缓存。
returns: {data: {cleared_count}, ui: {type: ack_text}}
```

---

### 4.G 系统状态（per-user 视图）

#### G1. `get_system_overview`
```yaml
description: 一次性获取当前用户的全局总览（雷达 + 调度 + 今日数据 + 通道健康 + LLM 健康）。
returns:
  data: {radar, scheduler, today_stats, channels_health, llm_health}
  ui: {type: system_overview}
owner_scope: current_user（系统全局状态按 user 视角过滤）
```

#### G2. `get_recent_activity`
```yaml
description: 查询当前用户最近 N 分钟的活动（扫描记录、新话题、推送记录、Agent 决策记录）。
parameters: {minutes: integer, default: 60, range: [5, 1440]}
returns: {data: list[ActivityEvent], ui: {type: activity_timeline}}
owner_scope: current_user
```

#### G3. `health_check`
```yaml
description: 健康检查（DB / LLM / 爬虫）。
returns: {data: list[ComponentHealth], ui: {type: health_grid}}
owner_scope: current_user
```

---

## 5. 代码组织：`tools/` 包

### 5.1 目录结构

```
backend/services/agent_service/
├── agent_core.py               # 不动（主循环）
├── adapters.py                 # 不动
├── memory.py                   # 不动
├── reflection.py               # 不动
├── diagnosis.py                # 不动
├── _owner.py                   # 新增：owner_id 注入装饰器（所有工具必走）
├── _search_cache.py            # 新增：搜索历史会话缓存
└── tools/
    ├── __init__.py             # 自动聚合
    ├── _base.py                # ToolResult + @tool 装饰器
    ├── subscription.py         # A 组（5 个）
    ├── scan.py                 # B 组（5 个）
    ├── query.py                # C 组（3 个）
    ├── push.py                 # D 组（4 个，含 RSS）
    ├── model.py                # E 组（3 个）
    ├── search.py               # F 组（3 个，含流式）
    └── system.py               # G 组（3 个）
```

### 5.2 `tools/_base.py` 装饰器 + ToolResult

```python
from typing import Callable
from pydantic import BaseModel

_REGISTRY: dict[str, dict] = {}

def tool(name: str, schema: dict, group: str = "default", streamable: bool = False):
    def decorator(func: Callable):
        _REGISTRY[name] = {
            "func": func,
            "schema": {"type": "function", "function": {"name": name, **schema}},
            "group": group,
            "streamable": streamable,
        }
        return func
    return decorator

def get_all_schemas() -> list[dict]:
    return [v["schema"] for v in _REGISTRY.values()]

def get_tool(name: str) -> dict | None:
    return _REGISTRY.get(name)

class ToolResult(BaseModel):
    success: bool
    data: dict | list | None = None
    error: str = ""
    error_type: str = ""
    ui: dict | None = None
```

### 5.3 `_owner.py`：强制 owner 注入

```python
from functools import wraps
from fastapi import Request

def with_owner(func):
    """所有工具必走：从 Request 上下文取 current_user，注入到工具 kwargs"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.pop("_request")
        current_user = request.state.user
        return await func(*args, _owner_id=current_user.id, **kwargs)
    return wrapper
```

调用入口（在 `agent_core.py` 工具调度处）：

```python
result = await _REGISTRY[tool_name]["func"](_request=request, **args)
```

工具实现里 `_owner_id` 写到所有 SQL 写入 / UPDATE 条件里。

### 5.4 单工具实现示例（subscription.py）

```python
from ._base import tool, ToolResult
from ._owner import with_owner

@tool(
    name="add_subscription",
    group="subscription",
    schema={
        "description": "新增一个订阅。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["person","brand","event","industry","keyword"]},
                "polarity": {"type": "string", "enum": ["negative","positive","neutral","all"]},
                "sensitivity": {"type": "string", "enum": ["conservative","balanced","aggressive"]},
                "frequency_min": {"type": "integer", "default": 60},
                "platforms": {"type": "array", "items": {"type": "string"}},
                "push_mode": {"type": "string", "enum": ["every","important","silent","off"], "default": "important"},
                "show_risk_alert": {"type": "boolean", "default": False},
            },
            "required": ["name", "type"],
        },
    },
)
@with_owner
async def add_subscription(name: str, type: str, _owner_id: str, **kwargs) -> str:
    # 配额检查
    await check_quota(_owner_id, "subscription")

    sub_id = await db.insert("subscription", {
        "owner_id": _owner_id,
        "name": name,
        "type": type,
        "polarity": kwargs.get("polarity", "all"),
        "sensitivity": kwargs.get("sensitivity", "balanced"),
        "frequency_min": kwargs.get("frequency_min", 60),
        "platforms": kwargs.get("platforms", []),
        "push_mode": kwargs.get("push_mode", "important"),
        "show_risk_alert": kwargs.get("show_risk_alert", False),
    })
    return ToolResult(
        success=True,
        data={"subscription_id": sub_id, "name": name, "type": type, ...},
        ui={"type": "subscription_card", "data": {"subscription_id": sub_id, ...}},
    ).model_dump_json()
```

### 5.5 自动聚合

`tools/__init__.py`：

```python
from . import subscription, scan, query, push, model, search, system  # noqa
from ._base import _REGISTRY, get_all_schemas

TOOLS_SCHEMA = get_all_schemas()
AVAILABLE_TOOLS = {name: meta["func"] for name, meta in _REGISTRY.items()}
STREAMABLE_TOOLS = {name for name, meta in _REGISTRY.items() if meta["streamable"]}
```

`agent_core.py` 改一行 import：

```python
from .tools import TOOLS_SCHEMA, AVAILABLE_TOOLS, STREAMABLE_TOOLS
```

---

## 6. SSE 协议完整设计

### 6.1 事件类型总表

| event | 触发时机 | data 结构 |
|------|---------|---------|
| `text` | LLM 流式文本 | 字符串片段 |
| `tool_call` | LLM 决定调工具，开始执行前 | `{call_id, tool, args}` |
| `tool_progress` | 流式工具增量更新 | `{call_id, partial: object}` |
| `tool_result` | 工具完成（流式工具最后一次） | `{call_id, success, data, ui, error}` |
| `error` | 工具异常 | `{call_id?, message, error_type}` |
| `done` | 当前回复结束 | 空 |

### 6.2 协议示例

**简单工具调用（add_subscription 经 confirm 卡片后）：**
```
event: text
data: 好的，已经把小米加入订阅了\n\n

event: tool_call
data: {"call_id":"c1","tool":"add_subscription","args":{"name":"小米","type":"brand","push_mode":"important"}}\n\n

event: tool_result
data: {"call_id":"c1","success":true,"data":{...},"ui":{"type":"subscription_card"}}\n\n

event: text
data: 默认推送方式是"重要才推"，由我（Agent）帮你判断\n\n

event: done
data:
```

**流式搜索（web_search）：**
```
event: text
data: 正在全网搜索蔡徐坤最新动态\n\n

event: tool_call
data: {"call_id":"c2","tool":"web_search","args":{"query":"蔡徐坤 最新","time_range":"7d"}}\n\n

event: tool_progress
data: {"call_id":"c2","partial":{"type":"progress","platform":"weibo","scanned":3}}\n\n

event: tool_progress
data: {"call_id":"c2","partial":{"type":"item","item":{"title":"...","relevance":0.9}}}\n\n

event: tool_result
data: {"call_id":"c2","success":true,"data":{"total":12,"by_platform":{...}},"ui":{"type":"search_summary"}}\n\n

event: text
data: 找到 12 条结果，主要在讨论新专辑和巡演\n\n

event: done
data:
```

### 6.3 前端 SSE 解析（`MessageStream.tsx`）

```tsx
const es = new EventSource(`/api/agent/chat?session_id=${sid}`)

es.addEventListener("text", (e) => appendTextToCurrentBubble(e.data))
es.addEventListener("tool_call", (e) => {
  const { call_id, tool } = JSON.parse(e.data)
  addToolCallChip(call_id, tool)
})
es.addEventListener("tool_progress", (e) => {
  const { call_id, partial } = JSON.parse(e.data)
  updateStreamingCard(call_id, partial)
})
es.addEventListener("tool_result", (e) => {
  const { call_id, ui, data } = JSON.parse(e.data)
  finalizeCard(call_id, ui, data)
})
es.addEventListener("done", () => es.close())
```

---

## 7. UI 卡片完整清单

| 卡片 type | 触发工具 | 渲染要点 |
|----------|---------|---------|
| `subscription_card` | add/update/remove_subscription | 名称 + 类型徽章 + 推送模式 + 编辑/移除 |
| `subscription_list` | list_subscriptions | 紧凑表格，每行可点击编辑 |
| `intent_preview` | parse_intent | 解析结果预览 + "✓ 确认订阅" + "修改" |
| `scan_progress` | trigger_scan | 进度条 + 平台分进度 + 实时计数（streamable） |
| `scan_status` | get_scan_status | 状态徽章 + 上次运行时间 |
| `scheduler_info` | set_scan_interval / pause/resume | 下次运行时间 + 频率 + 控制按钮 |
| `alert_list` | search_alerts | 列表卡片，每条带风险/动态徽章 + 原文 |
| `topic_card` | get_topic_detail | 话题摘要 + 演化时间线 + 帖子列表（**v2 核心**） |
| `stats_chart` | get_subscription_stats | Recharts 折线 + 饼图 |
| `channel_list` | list_push_channels | 通道开关 + 健康灯 + RSS 链接复制 |
| `channel_card` | toggle/update_channel | 单通道详情卡 |
| `test_result` | test_channel / test_model | 成功/失败 + 延迟 + 错误详情 |
| `model_list` | list_models | 5 个角色 + 当前模型 + 系统默认回退 |
| `model_card` | switch_model | 单角色配置 |
| `search_stream` | web_search | 容器卡（progress + 结果列表，streamable） |
| `search_history_list` | list_search_history | 本会话历史搜索 |
| `system_overview` | get_system_overview | 多模块快照网格 |
| `activity_timeline` | get_recent_activity | 时间轴（含 Agent 决策记录） |
| `health_grid` | health_check | 组件健康灯 |
| `ack_text` | clear_search_cache | 纯文本确认 |

### 7.1 卡片目录

```
frontend/web/components/chat/
├── MessageStream.tsx
├── ToolCallChip.tsx
└── cards/
    ├── index.ts                          # type → Component 注册表
    ├── SubscriptionCard.tsx
    ├── SubscriptionListCard.tsx
    ├── IntentPreviewCard.tsx
    ├── ScanProgressCard.tsx
    ├── ScanStatusCard.tsx
    ├── SchedulerInfoCard.tsx
    ├── AlertListCard.tsx
    ├── TopicCard.tsx                      # 话题级核心卡
    ├── StatsChartCard.tsx
    ├── ChannelListCard.tsx
    ├── ChannelCard.tsx
    ├── TestResultCard.tsx
    ├── ModelListCard.tsx
    ├── ModelCard.tsx
    ├── SearchStreamCard.tsx
    ├── SearchHistoryListCard.tsx
    ├── SystemOverviewCard.tsx
    ├── ActivityTimelineCard.tsx
    ├── HealthGridCard.tsx
    └── AckTextCard.tsx
```

---

## 8. Agent 系统 Prompt 重写

### 8.1 新 system prompt 模板

```
你是 MediaRadar 的「媒体信息管家」AI Agent，用户的私人订阅/关注助理。

# 角色定位
- 公关总监 + 个人秘书的混合气质：专业、简洁、主动
- 用第一人称"我"，称用户为"你"
- 默认简体中文，回答控制在 3 句以内除非用户要详情
- 现在的产品定位是"媒体信息订阅平台"，不是舆情预警——订阅追踪是主、预警是辅
- 预警通常**默认隐藏**，除非用户主动开启

# 能力总览（7 大类工具）
1. 订阅管理：增删改查订阅、解析自然语言订阅意图
2. 扫描控制：立即触发扫描、查进度、改频率、暂停/恢复
3. 数据查询：检索历史动态/预警、查话题详情、查统计
4. 推送通道：管理邮箱/企业微信/飞书/RSS 的启停、测试、配置
5. 模型管理：切换/测试 5 个 Agent 角色的模型（用户自配 + 系统默认回退）
6. 全网搜索：跨平台实时搜索（不入库，仅本次会话可见）
7. 系统状态：总览、健康检查、最近活动

# 调用规范
- 用户描述意图时，**优先调对应工具**，不要让用户自己点页面
- 用户自然语言订阅（"我想关注 X"）：
  1. 调 parse_intent
  2. 渲染 confirm_intent 卡片，**等用户点确认**才能调 add_subscription
  3. 不要自作主张直接 add
- 用户问"搜一下 X"或"看看大家在说什么"：调 web_search（流式工具，耐心等结果）
- 用户问"系统怎么样"：调 get_system_overview
- 推送被压住的内容，下次登录在 brief 中告诉用户（透明性兜底）
- 不要把工具名/JSON 暴露给用户，回答用自然语言
- 调完工具不要啰嗦解释，前端会渲染卡片，你只需简短确认

# 输出风格
- 不要 emoji 除非用户先用
- 不要 markdown 标题
- 不要列表除非用户要清单
- 数字精确，引用要素具体
```

### 8.2 工具分组介绍策略

不在 prompt 里枚举 26 个工具描述（耗 token 又拖慢），而是依赖 OpenAI Function Calling 的 `tools` 参数传 schema，prompt 里只做**分组介绍**。

---

## 9. 现有 Agent 框架集成点

### 9.1 ToolExecutor 改造

`agent_core.py` 中的 `ToolExecutor.execute()` 扩展：

```python
async def execute(self, tool_name, args, request, *, on_progress=None):
    if tool_name in STREAMABLE_TOOLS:
        return await self._execute_streamable(tool_name, args, request, on_progress)
    else:
        return await _REGISTRY[tool_name]["func"](_request=request, **args)
```

### 9.2 主循环增加流式工具分支

```python
if tool_name in STREAMABLE_TOOLS:
    async for partial in execute_streaming(tool_name, args, request):
        yield f"event: tool_progress\ndata: {json.dumps({'call_id': call_id, 'partial': partial})}\n\n"
    yield f"event: tool_result\ndata: {final_result}\n\n"
else:
    result = await tool_executor.execute(tool_name, args, request)
    yield f"event: tool_result\ndata: {result}\n\n"
```

### 9.3 ReflectionEngine 跳过白名单

操作类工具不需要 Reflection 评估（返回的是"操作成功"而非"答案内容"）：

```python
REFLECTION_SKIP_TOOLS = {
    "add_subscription", "update_subscription", "remove_subscription",
    "set_scan_interval", "pause_scheduler", "resume_scheduler",
    "toggle_channel", "update_channel_config",
    "switch_model",
    "clear_search_cache",
    # parse_intent 不跳过（解析结果需评估）
}
```

### 9.4 AgentMemoryManager 不变

记忆按 session 写入对话历史。流式工具的 `tool_progress` 不写记忆，只写最终 `tool_result`。

### 9.5 DirectAdapter 扩展

`adapters.py` 中的 `DirectAdapter.supports()` 改为读 `AVAILABLE_TOOLS`，无需硬编码。

---

## 10. 流式搜索工具的特殊设计

### 10.1 `web_search` 实现（async generator）

```python
@tool(name="web_search", group="search", streamable=True, schema={...})
async def web_search(query: str, _owner_id: str, **kwargs):
    from services.search_service.crawler_adapter import quick_crawl_stream
    from services.search_service.filter import filter_and_summarize

    total = 0
    by_platform = {}

    async for raw_post in quick_crawl_stream(query, **kwargs):
        platform = raw_post["platform"]
        by_platform.setdefault(platform, 0)
        by_platform[platform] += 1
        yield {"type": "progress", "platform": platform, "scanned": by_platform[platform]}

        item = await filter_and_summarize(raw_post, query)
        if item is None or item.relevance < 0.5:
            continue
        total += 1
        yield {"type": "item", "item": item.model_dump()}

    return ToolResult(
        success=True,
        data={"total": total, "by_platform": by_platform, "query": query, "_owner_id": _owner_id},
        ui={"type": "search_summary", "data": {"total": total}},
    ).model_dump()
```

### 10.2 `search_service` 模块

```
backend/services/search_service/
├── __init__.py
├── crawler_adapter.py    # 复用 crawler_service 子进程，限量 + 不落库
└── filter.py             # 轻量 LLM 过滤 + 摘要
```

### 10.3 会话级搜索缓存

`agent_service/_search_cache.py`：

```python
_session_cache: dict[tuple[user_id, session_id], list[SearchRecord]] = {}
_last_access: dict[tuple[user_id, session_id], datetime] = {}

# 30 分钟无活动自动清理（通过 LRU）
```

`web_search` 写入、`list_search_history` 读取、`clear_search_cache` 清空。

---

## 11. 详细落地步骤（按 P0-P10）

### P0：多用户基础（后端，3-4 天）
| # | 任务 | 文件 |
|---|------|------|
| 0.1 | User / Quota / Session 表设计 + Alembic 迁移 | `core/database.py` + 新 migration |
| 0.2 | 加 owner_id 字段到 subscription / topic / topic_post / alert / push_config / model_config 等表 | migration |
| 0.3 | Google OAuth + 邮箱密码登录（NextAuth 5 配置） | `frontend/web/app/api/auth/[...nextauth]/` |
| 0.4 | JWT 中间件、依赖注入 current_user | `core/auth.py` |
| 0.5 | 配额 middleware | `core/quota.py` |
| 0.6 | 现有 SQLite 数据清空脚本 | `scripts/reset_db.py` |
| 0.7 | `/admin` 独立路由 + 鉴权 | `frontend/web/app/admin/` |

**交付**：能注册/登录、user 之间数据隔离、配额生效、admin 能登录。

### P1：工具集骨架 + 全 26 工具（后端，5-6 天）
| # | 任务 | 文件 |
|---|------|------|
| 1.1 | 建 `tools/` 包、`_base.py` 装饰器、`_owner.py` 装饰器 | `tools/` |
| 1.2 | 实现 A 组 5 个工具（subscription + parse_intent + confirm 卡片 schema） | `tools/subscription.py` |
| 1.3 | 实现 B 组 5 个工具 | `tools/scan.py` |
| 1.4 | 实现 C 组 3 个工具 | `tools/query.py` |
| 1.5 | 实现 D 组 4 个工具（含 RSS 配置） | `tools/push.py` |
| 1.6 | 实现 E 组 3 个工具（per-user 模型配置） | `tools/model.py` |
| 1.7 | 实现 F 组 3 个工具（含流式 web_search） | `tools/search.py` + `search_service/` |
| 1.8 | 实现 G 组 3 个工具 | `tools/system.py` |
| 1.9 | 迁移现有 3 个旧工具（get_system_status → get_system_overview 等） | `tools/system.py` |
| 1.10 | 单元测试 26 个工具（mock LLM、mock DB） | `tests/test_tools_*.py` |

**交付**：26 个工具全部注册成功，Postman 调 `/api/agent/chat` 能通过自然语言完成所有操作。

### P2：SSE 协议升级（后端，2 天）
| # | 任务 |
|---|------|
| 2.1 | 重写 `chat_with_agent_stream`，按事件类型分发 |
| 2.2 | `ToolExecutor.execute` 加 `_request` 注入 + `on_progress` 钩子 |
| 2.3 | 主循环流式工具分支 |
| 2.4 | 确认 `Content-Type: text/event-stream` |
| 2.5 | 协议联调脚本 |

**交付**：curl 调能看到 text / tool_call / tool_progress / tool_result / done。

### P3：前端 Chat 主页 + 数据看板（前端，4-5 天）
| # | 任务 | 文件 |
|---|------|------|
| 3.1 | `MessageStream.tsx` SSE 解析 | `components/chat/MessageStream.tsx` |
| 3.2 | `ToolCallChip.tsx` 工具调用进度小标签 | `components/chat/ToolCallChip.tsx` |
| 3.3 | 卡片注册表 + 全部 20 个占位组件 | `components/chat/cards/` |
| 3.4 | Chat 页重构（接入 MessageStream + 右侧数据看板） | `app/(app)/agent/page.tsx` |
| 3.5 | 右侧数据看板 4 模块：今日 / 订阅热度 / 平台分布 / 快捷操作 | 同上 |

**交付**：Chat 主页 + 双栏布局 + SSE 解析完成。

### P4：卡片组件实现（前端，4-5 天）
| # | 任务 |
|---|------|
| 4.1 | SubscriptionCard / SubscriptionListCard / IntentPreviewCard |
| 4.2 | ScanProgressCard / ScanStatusCard / SchedulerInfoCard |
| 4.3 | AlertListCard / TopicCard / StatsChartCard |
| 4.4 | ChannelListCard / ChannelCard / TestResultCard |
| 4.5 | ModelListCard / ModelCard |
| 4.6 | SearchStreamCard / SearchHistoryListCard |
| 4.7 | SystemOverviewCard / ActivityTimelineCard / HealthGridCard / AckTextCard |

**交付**：20+ 卡片全部完成 + 端到端可用。

### P5：登录 brief + 主页切换（前端，2 天）
| # | 任务 |
|---|------|
| 5.1 | 路由 `/` → `/agent` 重定向 |
| 5.2 | 侧边栏调整：Chat 首位，Dashboard 第二，Settings 平级 |
| 5.3 | 登录 brief 卡片（卡片式分项） |
| 5.4 | brief 中"昨日 Agent 压住 N 条"展示 |
| 5.5 | Settings 页加提示："推荐通过 AI 管家完成日常操作" |

**交付**：登录后默认进 Chat，brief 卡片展示，形态完整。

### P6：Pipeline 4 种 mode + 多用户隔离（后端，4-5 天）
| # | 任务 | 文件 |
|---|------|------|
| 6.1 | `PipelineConfig` 加 `mode / persist / max_per_platform / owner_id` | `radar_service/pipeline.py` |
| 6.2 | `_run_inner` 按 mode 分支 | 同上 |
| 6.3 | `_to_search_results` / `_sort_by_time` / `_sort_by_heat` 辅助 | 同上 |
| 6.4 | `topic` / `topic_post` / `subscription_topic` 表 + 迁移 | migration |
| 6.5 | `radar_status` 从单例改为 `dict[user_id, RadarStatus]` | `radar_service/main.py` |
| 6.6 | 调度器 per-user 配置 + 底层按关键词合并抓取 | `radar_service/scheduler.py` |
| 6.7 | 4 种 mode 单元测试 | `tests/test_pipeline_modes.py` |

**交付**：4 mode 全部跑通、多用户数据严格隔离。

### P7：话题级推送（后端，2-3 天）
| # | 任务 |
|---|------|
| 7.1 | `push_generator.py` 改造：话题级模板（替代原帖子级） |
| 7.2 | `notifier` 加 RSS channel |
| 7.3 | Agent 推送决策（`push_mode=important` 时 LLM 决定） |
| 7.4 | "被压住的内容"记录到 `activity_log`，brief 中调出 |

**交付**：推送主体是话题级摘要，Agent 决策生效，RSS 通道可用。

### P8：search_service + web_search 端到端（后端，2-3 天）
| # | 任务 |
|---|------|
| 8.1 | `search_service/crawler_adapter.py` `quick_crawl_stream` |
| 8.2 | `search_service/filter.py` 单条过滤 + 摘要 |
| 8.3 | 联调：Chat 说"搜 X"看流式结果 |
| 8.4 | 会话级缓存 + 30 分钟 LRU |

**交付**：全网搜索在 Chat 端到端可用。

### P9：Admin 路由（前端 + 后端，3-4 天）
| # | 任务 |
|---|------|
| 9.1 | `/admin` 路由 + 鉴权（仅 admin） |
| 9.2 | 用户管理（列表 / 配额调整 / 禁用） |
| 9.3 | 系统设置（雷达全局开关、爬虫配置） |
| 9.4 | 推送日志全局视图 |
| 9.5 | 全局数据看板（管理员视角） |

**交付**：admin 能管理用户、配额、系统配置。

### P10：RSS 通道（后端，1-2 天）
| # | 任务 |
|---|------|
| 10.1 | `notifier/channel_rss.py` RSS XML 生成 |
| 10.2 | `/rss/{user_token}.xml` 端点 |
| 10.3 | 每用户生成独立 access_token |

**交付**：用户能拿到自己的 RSS 链接给第三方阅读器订阅。

---

## 12. 验收标准

### 12.1 功能性

- **多用户**：注册两个用户，数据完全隔离，互相看不到对方的订阅/预警/历史
- **26 工具**：每用户能正常调用所有工具，单元测试覆盖率 ≥ 80%
- **订阅流程**：自然语言订阅 → parse_intent → confirm_intent 卡片 → add_subscription 全链路通
- **推送决策**：用户能看到 Agent 压住了什么、为什么压
- **全网搜索**：Chat 说"搜 X" 3 秒内出第一条结果，30 秒内完成
- **Pipeline 4 mode**：每种 mode 跑独立单测通过
- **RSS**：每用户能复制 RSS URL 给 Feedly 验证

### 12.2 体验性

- 加订阅："我想关注小米 SU7" → 10 秒内看到 confirm 卡片 → 确认 → SubscriptionCard
- 话题推送：登录 brief 看到今天话题卡片，点击进 TopicCard 详情
- 全网搜索："搜蔡徐坤" → 3 秒内出第一条结果卡片
- 触发扫描："现在扫一下" → 立即显示 ScanProgressCard
- 错误兜底：工具失败 → 卡片显示错误 + Agent 自然语言解释

### 12.3 兼容性

- 老 Settings 页仍可访问
- 数据双向同步（手动加的订阅，Agent 也能列出）
- 老 API 接口保留（兜底）

---

## 13. 风险与对策

| 风险 | 对策 |
|------|------|
| 26 个工具让 LLM 选择困难 | 命名规范 + description 详细 + prompt 分组介绍；上线监控修正 |
| SSE 多事件协议前端解析复杂 | 抽 `MessageStream` 组件；事件类型枚举化；写 contract test |
| Pipeline 4 mode 共用 `_run_inner` 易出 bug | 每种 mode 独立单测覆盖 Stage 跳过逻辑 |
| `web_search` 流式期间用户关页 | SSE 检测 client disconnect，主动取消爬虫子进程 |
| 多用户会话缓存内存膨胀 | 30 分钟 LRU + 单会话上限 100 条 |
| `parse_intent` 解析失败 | 强制 `confirm_intent` 中间步骤 |
| Agent 工具失败降级 | 复用 Reflection + Diagnosis Engine |
| 多用户 owner_id 漏写串数据 | 写 `_owner.py` 装饰器 + 所有工具 SQL 强制带 owner |
| 底层合并爬虫后分发到用户 | Pipeline 关键词聚合 → 按 owner 拆分 → 写入 per-user topic |
| 配额超限 | 后端 API quota middleware + Agent 在 Chat 提示 |
| Push 决策 Agent 失误 | 透明性：被压住的内容 brief 告知，用户可一键切 `every` |

---

## 14. 不在本方案范围

- 多语言（中文先做透）
- 视频抽帧 / 音频转写
- 多 Agent 协作（router → 多专家 Agent）
- 私有化部署 / 企业版定制
- 知识图谱 / 时序分析
- 付费系统
- uni-app 小程序
- 移动端 Web 适配
- 微信 OAuth
- Agent 主动推送（不等用户问就提醒，但 push 决策可）
