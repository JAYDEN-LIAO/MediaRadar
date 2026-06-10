# MediaRadar V2 升级方案

> 制定时间：2026-06-10（v2 定位从「舆情监控」翻转为「媒体信息订阅/关注平台」）
> 适用范围：v2 上线计划下的产品形态升级、Agent 改造、多用户化
> 状态：方案已确认，待开发
> **配套文档**：`AGENT_REDESIGN.md` —— Agent 模块的完整改造细节（26 个工具 schema / SSE 协议 / UI 卡片 / 代码组织）

---

## 0. 战略定调

### 0.1 产品定位翻转

| 维度 | v1 旧定位 | v2 新定位 |
|------|---------|---------|
| 主叙事 | 舆情风险监控 | **媒体信息订阅/关注平台** |
| 主交互 | 仪表盘 + 手动表单 | **AI 管家 Chat**（Cursor 风格：左 Chat + 右数据看板） |
| 核心动作 | 监控负面预警 | **订阅追踪**（人物/品牌/事件/行业）+ 话题级推送 |
| 风险语义 | 核心 | **保留能力、UI 隐藏到 Settings** |
| 推送节奏 | 定时汇总 | **Agent 智能决定 + 手动兜底可强改** |
| 推送形式 | 帖子流 | **话题级推送**（Pipeline 聚类后产出） |
| 用户体系 | 单用户 | **多用户 SaaS + Admin 独立路由** |
| 全网搜索 | 无 | **并入 Agent F 组 `web_search` 流式工具**，无独立菜单 |

**核心判断**：`agent_core.py` 已有工业级 Agent 框架（TokenBudget / Memory / Reflection / Diagnosis / 直调-MCP 双适配 / 流式响应），但 `tools.py` 只挂了 3 个工具。本次升级 95% 的工作在 **工具集扩展 + 多用户化 + 前端可视化**，Agent 核心框架几乎不动。

### 0.2 参照形态

Cursor / Manus / Devin / Lindy 一类的 AI 主驾产品 —— **对话即操作**，传统后台作为"开盖维修"入口。

---

## 1. 产品形态对比

```
v1 旧形态                          v2 新形态
┌──────────────┐                ┌──────────────────────────┐
│  Dashboard   │ 主页            │  AI 管家 Chat     主页   │
├──────────────┤                ├──────────────────────────┤
│   Chat (辅)  │                │  右侧数据看板   始终可见 │
│   Settings   │                ├──────────────────────────┤
│   List       │                │  Dashboard    二级        │
└──────────────┘                │  Settings     平级可见    │
                                │  List         二级        │
                                └──────────────────────────┘

Agent 工具数：3                  Agent 工具数：26（一次性全上）
SSE：单一文本流                  SSE：text + tool_call + tool_progress + tool_result + done
Pipeline：单一链路               Pipeline：4 种 mode（full/trending/fan_track/quick_search）
搜索入口：无                     搜索入口：Agent 工具 web_search（流式）
预警：默认显示                   预警：默认隐藏到 Settings
关键词 → 订阅：术语统一为「订阅」 订阅类型：人物/品牌/事件/行业
```

★ 全网搜索仍不做独立菜单，**完全通过 Chat 触发**（详见 §6）。

---

## 2. 多用户 SaaS 架构

### 2.1 用户体系

| 角色 | 范围 | 入口 |
|------|------|------|
| **Admin**（超管 = 用户本人） | 全局：系统内部设置、用户管理、推送通道管理、爬虫配置 | `/admin` 独立路由、独立侧边栏 |
| **普通用户** | 自己的订阅、推送通道、模型配置、Chat 历史、搜索历史 | `/agent` 主页 + `/settings` 自己的设置 |

### 2.2 资源隔离边界

| 资源 | 隔离粒度 | 备注 |
|------|---------|------|
| 订阅（关键词/人物/品牌/事件/行业） | per user | 加 `owner_id` |
| 推送通道（邮箱/企微/飞书/RSS） | per user | RSS 路径可全局唯一 |
| 模型配置（5 个 Agent 角色） | per user | 用户自配 → 系统默认回退 |
| Chat 会话 / 搜索历史 | per user | 会话级内存缓存 |
| 历史动态 / 话题 | per user | 按 owner 过滤 |
| **爬虫任务** | **底层合并 + 上层隔离** | 同关键词全局抓 1 次，过滤/聚类/推送按用户独立 |
| 雷达全局开关 / 爬虫配置 | 全局（仅 admin） | 不开放给普通用户 |

### 2.3 认证与注册

- **认证方式**：Google OAuth + 邮箱密码（无微信 OAuth，v2 简化）
- **注册策略**：完全开放（任何人能注册）
- **会话管理**：每个用户独立 JWT，token 包含 user_id + role
- **配额外保护**：默认配额（20 订阅 / 30 天历史 / 200 chat 消息/月），admin 可在 `/admin/quota` 调整全局或单人

### 2.4 现有数据处理

- 现有 SQLite 中的数据 **重零开始**（v2 启动前清空）
- 重新初始化用户表 + 配额表 + 订阅/话题/预警表（全部带 owner_id）

---

## 3. 订阅系统设计

### 3.1 订阅类型（4 类 + 默认）

| 类型 | 适用对象 | 示例 |
|------|---------|------|
| `person` | 人物（明星/CEO/政治人物） | 蔡徐坤、雷军 |
| `brand` | 品牌/产品 | 小米 SU7、AirPods Pro |
| `event` | 热点事件/话题 | 618 大促、奥运会 |
| `industry` | 行业/领域 | 新能源汽车、AI |
| `keyword` | 兜底纯关键词 | 不明意图时使用 |

### 3.2 类型识别机制（Agent 猜 + 用户确认）

新增 **confirm_intent 卡片**（在 parse_intent 之后、add_subscription 之前插入）：

```
我：帮我盯一下小米 SU7

管家：好的，我猜这是一个「品牌/产品」订阅
  ┌── 📋 订阅预览 ─────────────┐
  │  小米 SU7                  │
  │  类型：品牌/产品（猜测）   │
  │  极性：中性                │
  │  频率：每 60 分钟          │
  │  平台：全平台              │
  │                            │
  │  [✓ 确认订阅]   [编辑]     │
  └────────────────────────────┘

管家：是不是这个意思？点确认我就加进去了
```

若用户修改 → 重新走一遍 add_subscription。LLM 不会"自作主张"落库。

### 3.3 订阅配置字段

```python
class Subscription(BaseModel):
    id: str
    owner_id: str
    type: Literal["person","brand","event","industry","keyword"]
    name: str                              # "蔡徐坤" / "小米 SU7"
    polarity: Literal["negative","positive","neutral","all"]
    sensitivity: Literal["conservative","balanced","aggressive"]
    frequency_min: int                     # 扫描频率
    platforms: list[str]                   # 限定平台（空=全部）
    push_mode: Literal["every","important","silent","off"]  # 推送强度
    show_risk_alert: bool = False          # 是否在动态里夹带预警（默认 False 隐藏预警）
    created_at: datetime
    updated_at: datetime
```

### 3.4 话题独立存储

新增 3 张表：

```sql
topic (                              -- 话题（跨订阅复用）
  id PK, owner_id, subscription_id,  -- 物理上仍按 owner 隔离
  title, summary,                    -- Agent 生成
  post_count, platform_dist,         -- 统计
  first_seen_at, last_seen_at,
  is_active,                         -- 还在被增量更新
  importance_score
)

topic_post (                         -- 话题-帖子关联
  topic_id FK, post_id, platform,
  published_at, engagement
)

subscription_topic (                 -- 订阅-话题关联（多对多）
  subscription_id, topic_id,
  first_subscribed_at
)
```

★ `topic` 表有 `owner_id` 保持隔离，**话题不跨用户共享**（虽然底层爬虫结果共享）。

---

## 4. 推送系统设计

### 4.1 推送决策（Agent 决定 + 手动兜底）

```
用户：小米 SU7 的推送怎么设的？
Agent：现在是「important」模式（仅重要动态才推），由我（Agent）决定
       昨天我压住了 3 条认为是普通讨论的，要不要看看？

  ┌── 📨 推送设置 ─────────┐
  │  推送强度：重要才推   │
  │  决策方式：Agent 智能  │
  │                        │
  │  切换：                  │
  │  ○ 推每条动态          │
  │  ● 重要才推（Agent）   │
  │  ○ 仅手动查看          │
  │  ○ 关闭                │
  │                        │
  │  [保存]                │
  └────────────────────────┘
```

**核心规则**：
- 每个订阅独立 `push_mode`：`every` / `important` / `silent` / `off`
- `important` 模式下由 Agent 决定推什么，**被压住的内容下次登录 brief 时告知用户**（透明性兜底）
- 用户可随时通过 Chat 改：`"把小米改成推每条"` → 调 `update_push_mode` 工具

### 4.2 推送通道

| 通道 | 类型 | v2 状态 | 实现 |
|------|------|---------|------|
| 邮箱 | SMTP | 已有 | `notifier/channel_email.py` 增强 |
| 企业微信 | Webhook | 已有 | `notifier/channel_wecom.py` |
| 飞书 | Webhook | 已有 | `notifier/channel_feishu.py` |
| **RSS** | URL 输出 | **v2 新增** | `notifier/channel_rss.py`，每用户生成唯一 token URL |
| Telegram | Bot | 不在 v2 范围 | v3 |
| 个人微信 | 公众号 | 不在 v2 范围 | v3 |

RSS 通道设计：每用户生成一个 `/rss/{user_token}.xml` 端点，第三方阅读器（Feedly / Inoreader / Reeder）订阅，实时刷出话题摘要。

### 4.3 推送内容形式：话题级

不再是单条帖子推送，而是话题级摘要：

```
📨 MediaRadar 推送

【蔡徐坤】巡演首站官宣
  微博热度 ▲ 200% · 涉及 12 条讨论
  摘要：蔡徐坤工作室官宣 2026 巡演首站北京...
  [查看完整话题 →]

【小米 SU7】投诉激增
  小红书 + 微博 双平台热度齐升
  摘要：多位车主反馈刹车异响问题...
  [查看完整话题 →]
```

Pipeline 走 `trending` 模式（聚类后按热度推送）成为默认主链路。

---

## 5. Pipeline 模式化

`PipelineConfig` 新增 `mode` 字段，`RadarPipeline.run()` 按 mode 跳过/启用对应 Stage。

| mode | 链路 | 适用场景 | v2 默认 |
|------|------|---------|---------|
| `full`（原默认） | Screener → Vision → Cluster → LangGraph 分析 → 预警 | 需要风险预警时 | 否（隐藏预警） |
| **`trending`** | Screener → Cluster → 按热度排序 | 推送主链路（话题级） | **是** |
| `fan_track` | Screener → 时间排序 | "盯一下蔡徐坤最新 5 条" | 是 |
| `quick_search` | Screener 轻量过滤，无聚类、无分析、不落库 | 全网搜索 | 是 |

### 5.1 关键改造点（`pipeline.py`）

```python
@dataclass
class PipelineConfig:
    # ... 原有字段
    mode: Literal["full","trending","fan_track","quick_search"] = "trending"
    persist: bool = True              # quick_search 强制 False
    max_per_platform: int = 0          # 0 = 不限；quick_search 默认 5
    owner_id: str                      # 多用户隔离关键字段

class RadarPipeline:
    async def _run_inner(self, posts, background_tasks):
        # Stage 1: Screener 永远跑（所有 mode 都需要相关性过滤）
        screener_result = await self.screener.run(posts)

        if self.config.mode == "quick_search":
            return self._to_search_results(screener_result.passed)

        if self.config.mode == "fan_track":
            return self._sort_by_time(screener_result.passed)

        # Stage 2: Vision（仅 full）
        vision_passed = await self.vision.run(screener_result.needs_vision)
        final_screened = screener_result.passed + vision_passed

        # Stage 3: Cluster（full / trending 都需要）
        clusters = self.cluster.run(final_screened)

        if self.config.mode == "trending":
            return self._sort_by_heat(clusters)              # 提前返回，不分析不预警

        # Stage 4+: LangGraph 分析 + 预警（仅 full）
        # ... 原有逻辑
```

### 5.2 多用户隔离实施

- `PipelineConfig` 加 `owner_id`
- `topic` / `topic_post` 写入时带 owner_id
- `radar_status` 从全局单例改为 `dict[user_id, RadarStatus]`
- Scheduler 调度时按用户组聚合关键词，全局只跑一轮抓取，结果按 owner 拆分发

---

## 6. 功能点 1：自然语言订阅（合并实现）

**实现路径**：Agent A 组 `parse_intent` → `confirm_intent` 卡片 → `add_subscription` 工具链。

**典型对话流**：

```
用户：我想关注小米的负面消息
Agent：[调用 parse_intent]
       → 解析为 {name:"小米", type:"brand", polarity:"negative",
                sensitivity:"aggressive", push_mode:"important"}
       [渲染 confirm_intent 卡片，等待用户确认]
用户：✓ 确认
Agent：[调用 add_subscription]
       → 渲染 SubscriptionCard：已订阅"小米"，每 30 分钟扫描
```

### 6.1 `parse_intent` 数据契约

```python
class SubscriptionIntent(BaseModel):
    name: str                                # "蔡徐坤" / "小米"
    type: Literal["person","brand","event","industry","keyword"]
    type_confidence: float                    # 0-1，用于卡片展示"猜测置信度"
    polarity: Literal["negative","positive","neutral","all"]
    sensitivity: Literal["conservative","balanced","aggressive"]
    push_mode: Literal["every","important","silent","off"]
    scene: str                                # "明星动态" / "品牌动态" / "产品测评"
    suggested_platforms: list[str] = []
    suggested_frequency_min: int = 60
    raw_input: str                            # 原始输入存档
```

`confirm_intent` 卡片：用户点击"✓ 确认订阅" → 调 `add_subscription`。若 LLM 猜错类型，用户可在卡片中点"修改"重选。

---

## 7. 功能点 2：全网媒体搜索（并入 Agent）

**实现路径**：Pipeline `quick_search` 模式 + 独立 `search_service` 后端模块 + **Agent 工具 `web_search`**（流式，不做独立菜单）。

### 7.1 后端模块

```
backend/services/search_service/
├── __init__.py
├── crawler_adapter.py    # 复用 crawler_service 子进程，限量 + 不落库 + 流式输出
└── filter.py             # 单条 LLM 过滤 + 一句话摘要
```

不再有 `api.py`（不暴露独立 HTTP 接口），统一通过 Agent 工具 `web_search` 调用。

### 7.2 调用链

```
用户在 Chat 中说"搜一下蔡徐坤最新动态"
   ↓
Agent LLM 决定调 web_search 工具
   ↓
agent_core 主循环识别为流式工具
   ↓
web_search → search_service.crawler_adapter.quick_crawl_stream()
   ↓
filter.filter_and_summarize() 单条过滤 + 摘要
   ↓
SSE event: tool_progress 每条增量推给前端
   ↓
前端 SearchStreamCard 实时追加结果
   ↓
搜索结束 → SSE event: tool_result 汇总（total、by_platform）
   ↓
Agent 用自然语言总结："找到 12 条，主要在讨论..."
```

### 7.3 体验

```
我：搜一下蔡徐坤最新动态
管家：好的，正在全网搜索

  ┌─ web_search ───────────────────────────────┐
  │ 进度：weibo 5/5 · xhs 4/5 · douyin 2/3    │
  │                                            │
  │ • 蔡徐坤新专辑《迷》数字销量破百万         │
  │   微博 · 2026-06-09 · 相关度 0.92         │
  │   销量破百万为今年华语男歌手第二...        │
  │                              [查看原文 →]  │
  │                                            │
  │ • 蔡徐坤巡演首站官宣                       │
  │   小红书 · 2026-06-08 · 相关度 0.85        │
  │   ...                                      │
  └────────────────────────────────────────────┘

管家：找到 12 条结果，主要集中在新专辑发布和巡演消息上
```

### 7.4 配套工具（F 组共 3 个）

| 工具 | 用途 |
|------|------|
| `web_search` | 流式全网搜索（核心） |
| `list_search_history` | 列出本会话搜索历史 |
| `clear_search_cache` | 清空当前会话缓存 |

数据特性：**会话级内存缓存**（30 分钟超时清理），不写数据库。

---

## 8. Agent 工具集（26 个，分 7 组）

> 完整 schema、参数、返回结构见 `AGENT_REDESIGN.md` §4。

| 组 | 工具数 | 关键工具 |
|----|------|---------|
| **A 订阅管理 + 意图解析** | 5 | `list_subscriptions`, `add_subscription`, `update_subscription`, `remove_subscription`, `parse_intent`（+ `confirm_intent` 卡片中间步骤） |
| **B 扫描 / 调度控制** | 5 | `trigger_scan`, `get_scan_status`, `set_scan_interval`, `pause_scheduler`, `resume_scheduler`, `get_next_run_time` |
| **C 数据查询** | 3 | `search_alerts`（含动态和预警两类）, `get_topic_detail`, `get_subscription_stats` |
| **D 推送通道** | 4 | `list_push_channels`, `toggle_channel`, `test_channel`, `update_channel_config` |
| **E 模型管理** | 3 | `list_models`, `switch_model`, `test_model` |
| **F 全网搜索** | 3 | `web_search`（流式）, `list_search_history`, `clear_search_cache` |
| **G 系统状态** | 3 | `get_system_overview`, `get_recent_activity`, `health_check` |

**v2 一次性全上**（P1 完整范围），按组别分文件实现：`tools/{keyword→subscription, scan, query, push, model, search, system}.py`。

★ 工具重命名：`keyword` → `subscription`（语义从"舆情关键词"翻转为"信息订阅"），所有原 keyword 工具改成 subscription。

---

## 9. SSE 协议升级

### 9.1 协议（多事件类型）

```
event: text
data: 好的，我帮你把小米加入订阅\n\n

event: tool_call
data: {"call_id":"c1","tool":"parse_intent","args":{"utterance":"关注小米"}}\n\n

event: tool_call
data: {"call_id":"c2","tool":"add_subscription","args":{"name":"小米","type":"brand",...}}\n\n

event: tool_result
data: {"call_id":"c1","success":true,"data":{...},"ui":{"type":"intent_preview"}}\n\n

event: tool_result
data: {"call_id":"c2","success":true,"data":{...},"ui":{"type":"subscription_card"}}\n\n

event: text
data: 已经加好啦，极性是负面、推送重要才推\n\n

event: done
data:
```

### 9.2 前端事件分流

- `text` → 流到文字气泡
- `tool_call` → 显示工具调用进度小标签（loading）
- `tool_progress` → 流式工具增量更新（如 web_search 的每条结果）
- `tool_result` → 根据 `ui.type` 渲染对应卡片（subscription / topic / search / alert / model / channel / scheduler / system...）
- `done` → 结束当前回复

---

## 10. 前端 Chat 主页（Cursor 风格）

### 10.1 路由调整

- `app/(app)/layout.tsx` 默认重定向：`/` → `/agent`
- 原 `/dashboard` / `/yq-list` 仍可访问，从主菜单第一位降为第二位
- `/settings` 平级保留

### 10.2 Chat 页布局

```
┌─────────────────────────────────────────────────────────┐
│  MediaRadar 管家                          ⚙  │  📡 │
├──────────────────────────┬──────────────────────────────┤
│  对话流（中央，约 60%）  │  右侧数据看板（约 40%）      │
│                          │                              │
│  ┌────────────────────┐  │  ┌──── 今日数据看板 ─────┐  │
│  │ 我：把小米加入订阅 │  │  │ 扫描 18 次 ✓          │  │
│  │                    │  │  │ 话题增量 ▲ 28%        │  │
│  │ 管家：好的 ✓       │  │  │  推 3 / 压 7         │  │
│  │ ┌────────────────┐ │  │  │  高危 0 · 中危 2      │  │
│  │ │ 小米            │ │  │  └─────────────────────┘  │
│  │ │ 类型：品牌      │ │  │  ┌── 订阅热度 ────────┐  │
│  │ │ 推送：重要才推  │ │  │  │ 小米   ▓▓▓▓▓░     │  │
│  │ │ [编辑] [移除]  │ │  │  │ 蔡徐坤 ▓▓▓░░░     │  │
│  │ └────────────────┘ │  │  │ OpenAI ▓░░░░░     │  │
│  └────────────────────┘  │  └─────────────────────┘  │
│                          │  ┌── 平台分布 ──────────┐  │
│  ┌────────────────────┐  │  │ 微博 45% 抖音 30%    │  │
│  │  想监控什么？/ 改 │  │  │ 小红书 25%            │  │
│  │  什么设置？        │  │  └─────────────────────┘  │
│  └────────────────────┘  │  ┌── 快捷操作 ──────────┐  │
│  快捷：[加订阅][扫描]    │  │ [立即扫描]            │  │
│        [看预警]          │  │ [查看话题]            │  │
│                          │  │ [推送日志]            │  │
│                          │  └─────────────────────┘  │
└──────────────────────────┴──────────────────────────────┘
```

### 10.3 登录 brief（卡片式分项）

```
管家：早上好，给你看一下今天的情况：

┌── 📊 今日总览 ──┐
│  扫描 18 次 ✓    │
│  新增话题 12     │
│  推送 3 · 压住 7 │
└──────────────┘

┌── 🔥 需要关注 ──┐
│ • 小米SU7 投诉激增│
│ • 蔡徐坤 巡演官宣 │
│ • OpenAI GPT-6   │
└──────────────┘

[查看话题] [触发扫描] [今日全部]
──────────
想了解哪条？
```

### 10.4 新增前端组件

```
frontend/web/components/chat/
├── MessageStream.tsx         # SSE 多事件解析
├── ToolCallChip.tsx          # 工具调用进度小标签
└── cards/
    ├── SubscriptionCard.tsx  # add/update/remove_subscription 结果
    ├── SubscriptionListCard.tsx
    ├── IntentPreviewCard.tsx # parse_intent 中间步骤 + confirm_intent
    ├── ScanProgressCard.tsx
    ├── TopicGroupCard.tsx    # 话题级呈现（核心）
    ├── AlertCard.tsx         # 预警（Settings 内出现）
    ├── ChannelCard.tsx
    ├── ModelCard.tsx
    ├── SearchStreamCard.tsx
    ├── SystemOverviewCard.tsx
    └── ... 共 20+ 卡片
```

---

## 11. 关键决策记录（v2 全部）

| # | 决策 | 结论 | 理由 |
|---|------|------|------|
| 1 | 产品定位 | **媒体信息订阅/关注平台**（不是舆情） | "更像是信息归类" |
| 2 | 预警语义 | **保留能力、UI 隐藏** | 订阅为主，预留在 Settings |
| 3 | 主页 | **Chat 主页 + Cursor 双栏** | AI 主驾形态 |
| 4 | 推送形式 | **话题级**（不是单帖） | Pipeline 聚类后输出 |
| 5 | 推送决策 | **Agent 决定 + 手动兜底** | 透明性：被压住的 brief 告知 |
| 6 | 多用户 | **整个系统多用户** | SaaS 形态 |
| 7 | Admin | **/admin 独立路由** | 与普通用户入口分离 |
| 8 | 认证 | **Google OAuth + 邮箱密码** | 砍掉微信 OAuth |
| 9 | 注册 | **完全开放** | 任何 Google/邮箱注册 |
| 10 | 配额 | **默认配额 + admin 可调** | 20 订阅 / 30 天 / 200 chat |
| 11 | 现有数据 | **重零开始** | 干净启动 |
| 12 | 订阅类型 | **4 类（人物/品牌/事件/行业）+ keyword 兜底** | 覆盖主要使用场景 |
| 13 | 类型识别 | **Agent 猜 + 用户卡片确认** | 智能化 + 兜底 |
| 14 | 话题存储 | **独立表（per owner）** | 跨订阅复用 + 历史追溯 |
| 15 | 全网搜索 | **Agent 工具 web_search（无独立菜单）** | 单一 Chat 入口 |
| 16 | 推送通道 | **邮箱/企微/飞书 + RSS** | RSS 是新增 |
| 17 | 数据保留 | **30 天原文 / 话题永久 / 预警永久** | 体积可控 |
| 18 | 爬虫 | **底层合并 + 上层隔离** | 同关键词抓 1 次，按 user 分发 |
| 19 | Pipeline 默认 | **`trending`（不是 full）** | 话题级推送为主 |
| 20 | Pipeline mode | **4 种全量实现** | 一次到位 |
| 21 | 工具数 | **26 一次性上** | P1 完整范围 |
| 22 | 模型配置 | **每用户自配 + 系统默认回退** | 灵活 + 兜底 |
| 23 | 破坏性操作 | **不需二次确认**（卡片撤销） | 信任 LLM |
| 24 | Web 适配 | **PC 优先**、手机不适配 | uni-app v2 冻结 |
| 25 | uni-app | **v2 冻结、v3 再说** | 节省资源 |

---

## 12. 落地分阶段（推荐顺序）

> 详细到文件级别的步骤见 `AGENT_REDESIGN.md` §11。

| 阶段 | 工作内容 | 价值 | 难度 |
|------|---------|------|------|
| **P0** | 多用户基础：DB 加 owner_id 字段、用户表、登录注册、配额 | 一切前提 | 中 |
| **P1** | 后端：Tool 集骨架 + A/B/C/D/E/F/G 全 26 工具 | Agent 真正"管事" | 中 |
| **P2** | 后端：SSE 协议升级 + agent_core 适配（含流式工具分支） | 协议先立 | 中 |
| **P3** | 前端：Chat 主页 + MessageStream + 右侧数据看板 | 体验闭环 | 中 |
| **P4** | 前端：20+ 卡片组件补全 | 全闭环 | 中 |
| **P5** | 前端：登录 brief + 主页切换 + Cursor 双栏 | 形态翻转 | 中 |
| **P6** | 后端：Pipeline 4 种 mode 全量实现 + 多用户隔离 | 扩展性铺路 | 高 |
| **P7** | 后端：topic / topic_post / subscription_topic 表 + 话题级推送 | 推送主体 | 中 |
| **P8** | 后端：search_service 模块 + `web_search` 流式工具 | 功能点 2 | 中 |
| **P9** | Admin 路由：用户管理 / 配额调整 / 推送日志 / 系统设置 | 收尾 | 中 |
| **P10** | RSS 通道实现 | 通道扩展 | 低 |

---

## 13. 技术风险与对策

| 风险 | 对策 |
|------|------|
| 工具数从 3 → 26，LLM 选择错误率上升 | 工具命名规范化（动词_对象）+ description 详细 + prompt 按 7 组分组介绍；上线监控 `AGENT_TOOL_CALLS` 修正 |
| SSE 多事件协议前端解析复杂 | 抽 `MessageStream` 组件统一处理；事件类型枚举化；写 contract test |
| Pipeline 4 种 mode 共用 `_run_inner` 易出 bug | 每种 mode 独立单元测试，覆盖 Stage 跳过逻辑 |
| `web_search` 流式期间用户关闭页面 | 后端 SSE 检测 client disconnect，主动取消爬虫子进程 |
| 会话搜索缓存内存膨胀 | 30 分钟超时清理 + 单会话上限 100 条 |
| `parse_intent` 解析失败导致订阅错误 | 强制中间步骤 `confirm_intent` 卡片，让用户确认 |
| Agent 工具调用失败降级 | 已有 ReflectionEngine + DiagnosisEngine 处理 |
| 多用户 owner_id 漏写导致数据串 | 写 DB 操作的统一 `with_owner()` 装饰器，强制传 owner |
| 底层合并爬虫结果分发到用户 | Pipeline 输出先按关键词聚合，再按 owner 拆分，写入每用户私有 topic 表 |
| 配额超限 | 后端 API 入口加 quota middleware；超额返回明确错误，Agent 在 Chat 中提示用户 |

---

## 14. 不在 v2 范围（明确划线）

- 多语言支持（中文先做透）
- 视频抽帧 / 音频转写（Qwen-VL 仅保留现有图片能力）
- 多 Agent 路由（单 Agent + 丰富 tool set 足够）
- 私有化部署 / 企业版定制
- 知识图谱 / 时序分析
- **付费系统**（默认配额够用，暂不做付费墙）
- uni-app 小程序（v2 冻结）
- 移动端 Web 适配（PC 优先）
- 微信 OAuth（v2 砍掉）
- 主动推送（Agent 决定推送 vs 用户主动拉取）
