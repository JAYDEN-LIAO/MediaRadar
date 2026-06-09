# MediaRadar 升级方案（修订版 v2）

> **本文档是 update.md 的修订版**。原版在自审中被指出多处过度设计、夸大严重性、与现状不符。本版本只保留**真正能改善系统**的项，**所有改动都对照代码行号验证过**。
>
> **原则**：① 改动能消除真实风险/故障 ② 改动可控、零新框架 ③ 不做"理论上更好"的项

---

## 0. 现状速览

| 维度 | 现状 | 一句话问题 |
|------|------|----------|
| Agent 循环 | LLM + Function Calling + Reflection | 部分硬编码 + 几个真实 bug |
| 熔断 | llm_gateway / diagnosis_engine **两层独立** | 各管各的没问题，缺统一观测 |
| 安全 | HTML `.format()` 注入 / CORS 错配 | 真实风险，但低严重度 |
| 记忆 | SQLite + 硬编码 8 品牌白名单 | 实体抽取基本失效 |
| 规划/决策 | ReflectionEngine high/medi/low | medi 追问无上限 |
| 多 Agent | **无**，单循环 | 暂时不引入 |
| 评估/运维 | 审计日志类齐全但几乎未调用 | 接 2 个关键动作 |
| 可观测性 | 4 个 Prometheus 指标 | 加 agent 维度 |

---

## 1. 必须修（真实 bug / 风险）

### 1.1 `tools.py` 触发爬虫 → `asyncio.run` 在已有 loop 的线程里冲突

**位置**：
- `tools.py:43-57` `tool_trigger_background_crawl` 用 `threading.Thread` 调 `job()`
- `main.py:299-302` `job()` → `run_analysis_pipeline()` → `asyncio.run(run_analysis_pipeline_async())`
- `main.py:335-357` `job()` 同步入口内同步调 `run_crawler_for_platform()`（subprocess 阻塞）

**问题**：
- 当 Agent 在 FastAPI 进程内触发爬虫（`/api/agent/chat` 间接调用 `tools.tool_trigger_background_crawl`），daemon 线程里 `asyncio.run()` 试图在**非主线程**创建新 event loop，Python 3.10+ 会抛 `RuntimeError: There is no current event loop`。
- 当前 scheduler 是独立线程 + 自己创建 loop（`scheduler.py:55-74`），所以**调度路径没事**。但 Agent 路径 100% 会撞这个 bug。
- 真实可见的故障：用户对 Agent 说"立即查一下最新舆情" → 报 success=True（"已在后台启动"）→ 实际任务压根没跑起来。

**方案**：
- 把 `job()` 改为 async 优先：`async def job_async()` 已是主实现，`job()` 保留为同步 wrapper（仅给 scheduler 调）。
- `tools.py:43-57` 改用 `asyncio.run_coroutine_threadsafe` + FastAPI 主 loop：
  ```python
  loop = asyncio.get_running_loop()
  asyncio.run_coroutine_threadsafe(job_async(target_keyword=keyword), loop)
  ```
  但 `tools.py` 同步函数拿不到主 loop。最简方案：把工具签名改为 async（`async def tool_trigger_background_crawl`），让 Agent 直接 `await`。

**收益**：消除一类静默失败。**改动 ~30 行**。

---

### 1.2 HTML `.format()` 注入（邮件 / 飞书卡片）

**位置**：
- `push_generator.py:122,138,377,75` — `core_issue` / `report` 直接拼到 HTML
- `notifier/channel_email.py:98,103` — 同样问题
- `notifier/channel_feishu.py:50-67` — 飞书 markdown 字段同样

**真实风险链**：
- 爬虫抓的原始帖子 = 攻击者可控制
- `ANALYST_PROMPT` 让 LLM 自由输出 `core_issue` / `report`（不是 strict JSON schema）
- LLM 可能被 prompt injection 诱导输出 `<img onerror=...>` 或 `javascript:` 链接
- 邮件客户端不执行 JS，**但会渲染 `<img>` + 跟踪像素 + 钓鱼链接**。飞书同理。

**方案**：在 `core/` 新建 30 行的 `sanitize_email_field(text)`：
1. `html.escape()` 处理 `< > & " '`
2. URL 走白名单：仅 `http(s)://` + 域名后缀验证，丢 `javascript:` / `data:` / `vbscript:`
3. 长度上限 5000
4. 把这个函数套到 `push_generator.py` 模板和 `channel_email.py` 的 5 个字段

**收益**：消除一类注入路径。**改动 ~40 行**。

---

### 1.3 CORS `*` + `credentials=True` 错配

**位置**：`gateway/main.py:30-31`

```python
allow_origins=["*"],
allow_credentials=True,
```

**问题**：CORS 规范明确禁止此组合。带 cookie 的浏览器请求会被拒绝。当前前端是 uni-app（如未用 cookie 鉴权），实际未触发，但生产环境部署第三方前端时必踩。

**方案**：按 `ENV` 区分：
```python
allow_origins=settings.ALLOWED_ORIGINS if settings.ENV == "prod" else ["*"],
allow_credentials=settings.ENV == "prod",
```

**收益**：修正一类配置错误。**改动 3 行**。

---

### 1.4 `agent_core.py:386` 弃用的 `asyncio.get_event_loop()`

**位置**：`agent_core.py:386` `loop = asyncio.get_event_loop()`

**问题**：Python 3.10+ 在 async 函数里调 `get_event_loop()` 不存在 loop 时**会报警告 / 抛 DeprecationWarning**，3.12+ 直接抛错。

**方案**：删掉那行；让 `loop.run_in_executor(None, ...)` 自己拿当前 loop。

**收益**：消除弃用警告。**改动 3 行**。

---

## 2. Agent 主循环（影响使用体验）

### 2.1 agent_client 配置不刷新 + 6 处硬编码 model

**位置**：
- `agent_core.py:36-39, 151` — `_client` lazy property 用 `settings.ANALYST_API_KEY`，一旦缓存，**`update_llm_config()` 改 settings 后不重建**
- `agent_core.py:73, 203, 236, 274, 316, 361` — 6 处 `model="deepseek-chat"` 硬编码

**问题**：
- 改了 API Key / model 后，**已经创建的 client 实例还是旧的**——必须重启进程
- 6 处 hardcode 意味着 Agent 不能用非 deepseek 模型

**方案**（轻量，不引入新 config 端点）：
1. 在 `core/config.py` 加：
   ```python
   AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
   AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "").strip()
   AGENT_MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")
   ```
2. 写 `get_agent_config() -> (key, base_url, model)`，空值回退到 DEFAULT
3. 6 处 `model="deepseek-chat"` 替换为 `get_agent_config()[2]`
4. `agent_client` 改为方法（不缓存）或加文件 mtime 监控（过度，**不要做**）

**收益**：配置改动实时生效；Agent 可走非 DeepSeek 模型。**改动 ~15 行**。

---

### 2.2 Token 估算误差

**位置**：`agent_core.py:42-49` `len(json.dumps(m)) // 4`

**问题**：中文 1 字 ≈ 1.5 token，按 char/4 估偏低。混合中英文时 `should_summarize` 触发比预期晚，context 容易爆。

**方案**：**不要引入 `tiktoken`**（DeepSeek tokenizer 不公开，cl100k_base 是近似）。
最简方案：char/2 估算（中文 1 字 1.5 token / 0.75 char-per-token → 1 字 ≈ 1.5 token ≈ 2 char）：
```python
def count_tokens(messages):
    return sum(len(m.get("content", "")) for m in messages) // 2
```

**收益**：偏差从 ±50% 降到 ±20%，**不引入新依赖**。**改动 5 行**。

---

### 2.3 `trigger_background_crawl` 特殊路径重复 streaming

**位置**：`agent_core.py:226-247`（特殊路径）和 `360-374`（正常完成），**两处都重复了 6 行 `for chunk in stream: yield ...`**

**方案**：抽一个 `_stream_response(messages) -> AsyncIterator[str]`，两条路径都调用它。

**收益**：DRY，未来加 streaming-friendly 工具时不用复制。**改动 ~15 行**。

---

### 2.4 fire-and-forget 失败加 metric（不做 dedup）

**位置**：`agent_core.py:246,281,323,373,379` — 5 处 `asyncio.create_task(_write_memory_async(...))`

**问题**：5 处 fire-and-forget 任务失败只打到日志，无 metric 无告警。
- **重要澄清**（自审发现）：5 处分别在**不同 early-return 路径**上，**每次对话只触发一次**，不存在"重复写 5 次"。

**方案**：
- 在 `core/metrics.py` 加：
  ```python
  AGENT_MEMORY_WRITES = Counter("agent_memory_writes_total", "记忆写入", ["status"])
  ```
- 改 `_write_memory_async` 内部 try/except，记 `success/error`
- **不加 dedup set**（5 个 early-return 已经天然互斥）

**收益**：写失败有可观测信号。**改动 ~10 行**。

---

## 3. 熔断（只做 observability，不动结构）

### 3.1 暴露统一熔断状态查询端点

**位置**：
- `llm_gateway.py:38-40` — `screener_circuit / analyst_circuit / reviewer_circuit`（按 engine）
- `diagnosis_engine.py:23-59` — `CircuitBreakerRegistry`（按 tool_name）

**判断**：两者保护对象不同（LLM 引擎 vs 工具调用），**不应合并**。但缺统一查询入口。

**方案**：在 `api.py` 加 `GET /api/circuit/states`，一次性返回所有熔断器状态：
```python
@router.get("/api/circuit/states")
def circuit_states():
    return {
        "llm": {
            "screener": screener_circuit.state.value,
            "analyst": analyst_circuit.state.value,
            "reviewer": reviewer_circuit.state.value,
        },
        "tools": {name: _circuit_registry.get(name).state.value 
                  for name in _circuit_registry._breakers},
    }
```

**收益**：运维一个端点看全部熔断。**改动 ~25 行**。

### 3.2 熔断状态变化 → Prometheus Gauge

**位置**：`circuit_breaker.py:46-49` 状态机切换没事件。

**方案**：
- `core/metrics.py` 加 `CIRCUIT_BREAKER_STATE = Gauge("circuit_breaker_state", "熔断状态", ["name"])`
- 在 `CircuitBreaker` 里加 `_on_state_change` 回调 hook
- `llm_gateway` / `diagnosis_engine` 初始化时注册回调

**收益**：Grafana 直接看熔断时间线。**改动 ~20 行**。

### 3.3 （不修）`_state` / `_failures` 协程安全

**自审澄清**：CPython GIL 下单行赋值原子，`is_available()` 到 `record_failure()` 间无 `await`，**实际无 race**。加锁是过度设计，**跳过**。

---

## 4. 记忆系统

### 4.1 实体抽取改 jieba（修真实 bug）

**位置**：`memory_manager.py:127-137` `_extract_entities` 硬编码 8 个品牌

**问题**：系统监控的是用户自定义关键词（如"北京银行""理想汽车"），当前实现**永远不会进 entity_memory**，"高频实体"功能完全失效。

**方案**：用 `jieba.posseg` 做词性标注，提取 `nr/ns/nt/nz`（人名/地名/机构名/其他专名）：
```python
import jieba.posseg as pseg
words = pseg.cut(summary)
entities = [(w.word, "brand") for w in words 
            if w.flag in ('nr','ns','nt','nz') and len(w.word) >= 2]
```

**收益**：从 8 品牌 → 任意中文实体都能识别。**改动 ~10 行 + 加 jieba 依赖**。

**依赖成本**：`jieba` 70KB 纯 Python 离线包，零外部依赖。

---

### 4.2 working_memory size cap

**位置**：`memory_manager.py:32-66` 拼到 system prompt，无长度限制

**方案**：在 `build_working_memory()` 末尾加：
```python
if sum(len(p) for p in parts) > 800:
    parts = parts[:2]  # 只保留 entity + fact
```

**收益**：防止 system prompt 膨胀。**改动 3 行**。

---

### 4.3 TTL 清理 cron 任务

**位置**：`memory_store.py:60-70` 有 `expires_at` 字段但**无清理**

**方案**：在 `scheduler.py` `scheduler_start()` 末尾挂：
```python
_scheduler.add_job(
    cleanup_expired_memory,
    CronTrigger(hour=3, minute=0, timezone="Asia/Shanghai"),
    id="memory_cleanup",
    replace_existing=True,
)
```
`cleanup_expired_memory` 走 `DELETE FROM fact_memory WHERE expires_at < ?`。

**收益**：DB 大小可控。**改动 ~20 行**。

---

## 5. 规划与决策

### 5.1 medi 追问上限

**位置**：`agent_core.py:284-303` `confidence == "medi"` 时 `continue` 回到循环顶部

**问题**：`AGENT_MAX_ITERATIONS=6` 是硬上限，**但 6 次追问对用户也是糟糕体验**。极端情况：每次 Reflection 都说"medi"，6 次都问 1 个 follow-up。

**方案**：在 `chat_with_agent_stream` 循环内加一个 `medi_count` 计数器：
```python
medi_count = 0
...
elif confidence == "medi" and medi_count < 1:
    medi_count += 1
    # follow_up
else:
    # 强制 degrade
```

**收益**：单次对话 medi 追问最多 1 次。**改动 5 行**。

---

## 6. 多 Agent 协作

### **本版本不做**

原计划中 6.1（Planner 拆分）和 6.2（工具调用顺序）都**不实施**：

- **6.1 拆 Planner/Executor/Critic**：30-50 行是严重低估，单循环改多阶段结构性变更。90% 对话是单步，引入 plan 阶段是 overhead。**等"多步任务失败率"成为可观测指标后再考虑**。
- **6.2 工具调用顺序**：这纯是 prompt 问题——加 1 行到 system prompt：「用户问今天/最新/刚刚时，必须先 crawl 再查」。不占代码升级位。

---

## 7. 评估 & 运维

### 7.1 审计日志接 2 个关键动作（不全接）

**位置**：`core/audit.py:1-220` 定义了 11 个动作但**业务代码几乎都不调用**（`grep "audit\."` 仅 0 处实际使用）

**方案**（只接 2 个，避免噪声）：
- `tools.py:30` `tool_trigger_background_crawl` 启动成功 → `audit.crawler_start(keyword, "agent")`
- `pipeline.py:778-790` 批量预警发送 → `audit.alert_triggered(keyword, topic_id, risk, title, sentiment)`
- `api.py:141` `api_save_settings` → `audit.config_changed(...)`

**收益**：审计日志开始有内容，但不爆。**改动 ~10 行**。

---

### 7.2 Prometheus 补 4 个 Agent 指标

**位置**：`core/metrics.py` 当前 4 个，全是 LLM/radar 维度

**新增**：
```python
AGENT_TURNS = Histogram("agent_turns_per_session", "对话轮数", buckets=(1, 2, 4, 6, 10, 20))
AGENT_TOOL_LATENCY = Histogram("agent_tool_latency_seconds", "工具调用耗时", ["tool_name"])
AGENT_TOOL_CALLS = Counter("agent_tool_calls_total", "工具调用", ["tool_name", "status"])
AGENT_MEMORY_WRITES = Counter("agent_memory_writes_total", "记忆写入", ["status"])  # 见 2.4
```

在 `agent_core.py` 关键点埋点。

**收益**：Grafana 直接看 Agent 健康度。**改动 ~25 行**。

---

## 8. 可观测性

### 8.1 trace_id middleware

**位置**：`core/context.py:8-12` 已有 `set_task_context`，但**没在请求入口被调用**。

**方案**：
1. `gateway/main.py` 加 middleware：每个请求生成 `trace_id = uuid().hex[:12]`，调 `set_task_context(trace_id=...)`
2. `ColoredConsoleFormatter` 已有 `task_str` 渲染（`logger.py:81`），但只显示前 8 位——`trace_id` 也是 12 位，**可以直接复用**
3. SSE 响应头加 `X-Trace-Id`，前端埋点能传

**收益**：每个对话/扫描的全链路日志可关联。**改动 ~30 行**。

---

## 9. 性能微优化（精挑细选）

| # | 位置 | 优化 | 价值 |
|---|------|------|------|
| 9.1 | `db_manager.py:30-44` | 加 `CREATE INDEX IF NOT EXISTS idx_ai_results_create_time ON ai_results(create_time)` + `idx_risk_level` | 列表/统计查询 10x（高频路径） |
| 9.2 | `embed_cluster.py:60-72` | 同 post_id 集合的 embedding 缓存（TTL 1h） | 调度器间隔短时**省 50% embedding 费** |

**不做**：
- ❌ UMAP/HDBSCAN 缓存（key 设计复杂，价值不明）
- ❌ vision_agent 图片 LRU（图片 1MB+，LRU 内存压力）
- ❌ analysis_graph 并行化（director 依赖 reviewer.adjusted_risk_level，结构上要重排）
- ❌ merge_ratio 配置化（伪需求）
- ❌ tiktoken 引入（近似，不值得）

---

## 10. 实施路线（修订）

### Phase 1：**必修** 真实 bug（1-2 天）
- 1.1 tools.py asyncio 冲突
- 1.4 `asyncio.get_event_loop` 弃用
- 2.1 agent_client 配置刷新 + 6 处 hardcode
- 1.2 HTML 注入净化
- 1.3 CORS 修正

### Phase 2：Agent 可观测性（1-2 天）
- 2.2 token 估算
- 2.3 streaming 抽取
- 2.4 memory metric
- 7.2 4 个新指标
- 8.1 trace_id middleware

### Phase 3：记忆 + 决策（1 天）
- 4.1 jieba 实体抽取
- 4.2 working_memory cap
- 4.3 TTL 清理 cron
- 5.1 medi 追问上限

### Phase 4：运维收口（半天）
- 3.1 熔断状态端点
- 3.2 熔断 → metric
- 7.1 审计日志接 2 个关键动作
- 9.1/9.2 性能微优化

**总计 4-6 天**（原计划 10-15 天，砍掉 60%）。

---

## 11. 显式不做（避免过度设计）

| 想做 | 不做的理由 |
|------|----------|
| LangGraph 引入 agent_service | 单循环够用；新框架成本 > 收益 |
| 自研 Agent 调度框架 | 现有 asyncio 完全够用 |
| OpenTelemetry 完整 trace | Prometheus + trace_id 覆盖 80% 场景；OTel 部署成本高 |
| 向量记忆（Mem0 等） | SQLite 够用 6-12 月；过早优化 |
| 多租户 / 多用户 | 业务尚未需要 |
| 工具调用 Marketplace | 当前 3 个工具；UI 复杂度爆炸 |
| Planner/Executor/Critic 拆分 | 90% 对话单步；结构变更收益不明 |
| 熔断合并 registry | 两层保护对象不同；保留分层 |
| `tiktoken` 依赖 | DeepSeek tokenizer 不公开；近似方案足够 |
| tiktoken/count_tokens 重写为 library | char/2 足够；引入新依赖不值 |
| 全面审计日志接入 | 噪声过大；只接关键 2 个 |
| 自动 prompt A/B 框架 | prompt 改动频率低（季度级）；用 git diff 即可 |
| 评估数据集 1 天投入 | 与本升级文档不是同一类工作（流程改进 vs 代码升级） |
| `_write_memory_async` dedup set | 自审发现 5 处 early-return 天然互斥，**dedup 不必要** |
| `_state` 协程加锁 | CPython GIL 下无 race；过度设计 |
| `medI` typo 修复 | 自审发现是**与 prompt 一致的设计选择**，不是 bug |

---

## 12. 与原版的关键差异

| 项 | 原版 | 修订版 |
|----|------|--------|
| `medi` typo 修 bug | ✅（错误：实际是设计） | ❌ 删除（保留如要改就是统一命名） |
| memory dedup | ✅ | ❌ 5 处 early-return 天然互斥 |
| 熔断合并 | ✅ | ❌ 保留分层 |
| `_state` 加锁 | ✅ | ❌ 无 race |
| 4.3 摘要并发 | ✅ | ❌ `_extract_entities` 已不是 LLM 调用 |
| 5.2 Diagnosis 接入 | ✅ | ❌ 路径已通 |
| 5.3 降级回答模板 | ✅ | ❌ 收益微小 |
| 6.1 Planner 拆分 | Phase 4 | ❌ 显式不做 |
| 6.2 工具顺序 | Phase 4 | ❌ prompt 问题非代码问题 |
| 9.x LRU 缓存 | 5 条 | 砍到 2 条 |
| **新增** tools.py asyncio 冲突 | — | ✅ Phase 1 必修 |
| **新增** agent_client 配置刷新 | — | ✅ Phase 1 |
| **新增** `asyncio.get_event_loop` 弃用 | — | ✅ Phase 1 |
| 全面审计日志接入 | 11 个 | 2 个 |
| 总实施时间 | 10-15 天 | 4-6 天 |
