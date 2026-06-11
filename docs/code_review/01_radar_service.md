# 模块审查详情 — radar_service + notifier

> 范围：`backend/services/radar_service/` 全部 + `notifier/` 包
> 文件数：14（主）+ 8（notifier）= 22

---

## A. 死代码清单

| # | 文件:行 | 符号 | 说明 |
|---|--------|------|------|
| 1 | `llm_gateway.py:38` | `screener_circuit` | 创建但 `circuit.call()` 从未触发；`get_all_breakers` 把它放进列表但**未激活** |
| 2 | `push_generator.py:10` | `import json` | 顶层冗余；函数内 `import json` 即可 |
| 3 | `channel_rss.py:12` | `import json` | 整个文件未使用 |
| 4 | `channel_rss.py:13` | `import os` | 整个文件未使用（`BASE_DIR` 用过一次 `os.path.dirname` 后无再使用） |
| 5 | `channel_rss.py:15` | `from typing import Optional` | 函数签名未使用 `Optional` |
| 6 | `notifier/base.py:3` | `from typing import Optional` | `NotifierBase` 中无 `Optional` 使用 |
| 7 | `notifier/models.py:63` | `class AllPushConfigs` | 被 `__init__.py:33` 和 `registry.py:9` 导入，但**全代码库无任何实例化** |
| 8 | `notifier/registry.py:17` | `from .channel_rss import generate_rss_xml` | 重复导入；`api.py:1067` 已直接 import |
| 9 | `db_manager.py:6` | `import threading` | 全文无 `threading.Thread` / `threading.Lock` |
| 10 | `db_manager.py:490-503` | `update_ai_result_email_html` | 无任何外部调用（grep 全文） |
| 11 | `main.py:4,103-108,383-384` | `import schedule` + `daily_summary_job` + `schedule.every().day.at("09:00").do(job)` | 调度已迁到 `scheduler.py`（APScheduler），旧路径仅 `__main__` 时生效 |
| 12 | `main.py:103-108` | `daily_summary_job` 函数 | 注释明确标 deprecated，函数体只有日志，从未被新代码调用 |

**死代码总计**：12 处

---

## B. 断裂的调用链

### B1. `topic_tracker.build_evolution_timeline` 返回值缺 `cluster_summary`

- **被调用方** `topic_tracker.py:268` 返回 dict 包含：`is_new_topic` / `topic_id` / `total_scan_count` / `total_post_count` / `duration_days` / `risk_evolution_path` / `current_risk_level` / `evolution_signal` / `timeline` — **无 `cluster_summary` 键**
- **调用方** `pipeline.py:652`:
  ```python
  cluster_summary=evolution_timeline.get("cluster_summary", ""),
  ```
- **后果**：`cluster_summary` 恒为空字符串，写入 Qdrant 后该字段**永远为空**
- **修复**：在 `topic_tracker.py` 返回 dict 中添加 `"cluster_summary": current_topic.get("cluster_summary", "")`

### B2. `llm_gateway.call_llm` 熔断器未覆盖 Screener

- `screener_circuit` 已创建但无 `call()` 调用
- `pipeline.py` 的 Screener 阶段直接调 `call_llm`，无任何熔断保护
- 与 Analyst/Reviewer 的熔断不对等

### B3. `topic_aggregator._calculate_risk_class` 与 `risk_class` 字段语义不一致

- `topic_aggregator.py:103-108`：当 LLM 返回 `sentiment ∈ {negative, positive, neutral}` 时，**直接用 sentiment 覆盖 risk_class**
- `_calculate_risk_class`（line 167-169）原本按 `risk_level >= 4 → "negative"` / `risk_level <= 2 → "positive"` 映射
- **后果**：风险语义和情感语义在前端混淆。"正面"实际可能是低风险舆情，也可能是 positive sentiment

### B4. `push_generator.py:531-538` SQL join 缺 owner_id 过滤

```python
SELECT p.url FROM topic_posts tp
JOIN ai_results p ON tp.post_id = p.post_id
WHERE tp.topic_id = ? AND tp.is_current = 1
LIMIT 5
```

`ai_results` 表有 `owner_id` 列（WS4.6 添加），但 join 条件未过滤 → 可能跨用户边界。

### B5. `audit.py:76` 跨服务 import 失败静默降级

```python
try:
    from services.radar_service.db_manager import insert_audit_log
except Exception:
    insert_audit_log = None
```

若 radar_service 未启动，审计日志**只写文件不写 DB**，且无告警。

---

## C. 跨文件契约不一致

| 问题 | 位置 A | 位置 B | 详情 |
|------|--------|--------|------|
| Schema 漂移 | `db_manager.py:226` quota 建表 | `quota_db.py:24-37` ALTER | quota 表 scan 相关列（`scan_interval_min` / `scan_start_time` / `scan_paused`）只在 quota_db.py ALTER 阶段添加；db_manager.py CREATE 不含 |
| 重复建表 | `db_manager.py:56-66` | `db_manager.py:138-149` | 两处定义 `audit_log` 表（第二个多 `owner_id` 列） |
| 批量推送签名 | `notifier/__init__.py` `send_batch_alert(owner_id, keyword, platform, alerts)` | `scheduler.py:366` 调用 `send_alert(...)` | `send_alert` 与 `send_batch_alert` 行为差异未文档化；scheduler 走 `send_alert` 传 `email_html`，但批量推送不支持此参数 |
| 类型注解 | `push_generator.py:1127` `def generate_batch_push_html(keyword, platform, alerts: list)` | `channel_email.py:118` 调用 | 应改为 `alerts: list[AlertPayload]` |
| alert_recommendation 死参数 | `db_manager.py:553-585` UPDATE 语句 | SELECT 列表 | SET 含 `alert_recommendation = ?` 但 SELECT 不提供对应字段值，导致 `COALESCE(NULLIF('', ''), alert_recommendation)` 始终返回原值 |

---

## D. Notifier 包详细一致性

### D1. 4 channel 实现完整性

| Channel | 继承 NotifierBase | send | send_batch | 签名 (AlertPayload→bool) | should_send | build_title | PushChannel enum |
|---------|------------------|------|-----------|--------------------------|-------------|-------------|------------------|
| Email | ✅ | ✅ | ✅ | ✅ | ✅ `risk_level >= min_level` | ✅ | ✅ EMAIL |
| WeCom | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ WECOM |
| Feishu | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ FEISHU |
| RSS | N/A (pull) | N/A | N/A | N/A | N/A | N/A | ✅ RSS（registry 不注册） |

### D2. `__init__.py` 导出函数签名

```python
send_alert(owner_id, keyword, platform, risk_level, risk_class,
           core_issue, report, urls, topic_id="", post_count=1, email_html="")
send_batch_alert(owner_id, keyword, platform, alerts: list[AlertPayload])
reload_registry(owner_id: Optional[str] = None)
test_channel(channel: PushChannel, config: dict) -> bool
```

调用处匹配：
- `scheduler.py:366` → `send_alert` ✅
- `pipeline.py:820` → `send_batch_alert` ✅
- `api.py:850,873` → `reload_registry` ✅
- `api.py:880` → `test_channel` ✅

### D3. RSS 设计正确性

`registry._skip_rss()` 正确排除 RSS。RSS 由 `api.py:/rss/{token}.xml` 直接生成 XML，是 pull 模式而非 push。

**`load_configs` 不处理 RSS 是正确的设计**，不应在 registry 中注册。

---

## E. LangGraph 子图分析

文件：`analysis_graph.py`

**子图节点**：analyst → reviewer → director

- State schema 与节点输入/输出自洽 ✅
- 风险等级判定、复核、简报生成闭环完整 ✅
- **建议**：为 Screener 节点补加熔断保护（与 Analyst/Reviewer 对齐）

---

## F. Push Generator 模板

`push_generator.py` 中三个 HTML 模板（CLAUDE.md 提及）：
- `BATCH_PUSH_HTML_TEMPLATE`（批量预警）✅
- `PUSH_HTML_TEMPLATE`（单条预警）✅
- `DAILY_SUMMARY_TEMPLATE`（每日简报）✅

均支持 `<details>` 可折叠。

`generate_batch_push_html` 内部直接索引 `alert.risk_class` / `alert.risk_level` / `alert.urls` / `alert.report` / `alert.core_issue` / `alert.post_count`，**与 `AlertPayload` 字段一致**。

---

## G. 建议删除清单（10 项）

1. `llm_gateway.py:38` — `screener_circuit`（或接入 Screener）
2. `push_generator.py:10` — 顶层 `import json`
3. `channel_rss.py:12-15` — 三个未使用 import
4. `notifier/base.py:3` — `Optional`
5. `notifier/models.py:63` — `AllPushConfigs` 类
6. `notifier/registry.py:17` — `generate_rss_xml` 重复 import
7. `db_manager.py:6` — `threading`
8. `db_manager.py:490-503` — `update_ai_result_email_html`（或加调用方）
9. `main.py:4,103-108,383-384` — `schedule` + `daily_summary_job` + `__main__` 路径
10. `db_manager.py:56-66 vs 138-149` — 合并 audit_log 重复建表

---

## H. 必须修复清单（5 项）

1. `topic_tracker.py:268` — 返回 dict 加 `cluster_summary` 键
2. `topic_aggregator.py:103-108` — 分离 sentiment 与 risk_class
3. `push_generator.py:531-538` — SQL join 加 `owner_id` 过滤
4. `llm_gateway.call_llm` — 为 Screener 阶段接入熔断（或删除未使用的 `screener_circuit`）
5. `db_manager.py:226` — quota 表 CREATE 包含 scan 配置列，与 quota_db.py 保持一致
