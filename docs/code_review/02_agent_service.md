# 模块审查详情 — agent_service + tools + memory

> 范围：`backend/services/agent_service/` 全部
> 文件数：根 4 + tools 9 + memory 2 = 15

---

## A. 死代码清单

| # | 文件:行 | 符号 | 说明 |
|---|--------|------|------|
| 1 | ~~`tools/system.py:80`~~ | ~~`_removed_trigger_background_crawl`~~ | ~~函数名已 `_removed_` 前缀但 `@tool` 装饰器仍注册为 `trigger_background_crawl`，与 `agent_core.py:375` 的特殊路径分支**同时存在**，造成 LLM 调用歧义~~ **✅ 已解决（2026-06-11）** |
| 2 | `tools/subscription.py:13` | `import json` | 全文未使用（所有 JSON 通过 `ToolResult.to_json()`） |
| 3 | `agent_core.py:304` | `medi_count` | 在 for 循环内声明，**每次重置为 0**；注释"每 session 最多 1 次"但作用域错误，实际无限流作用 |
| 4 | `agent_core.py:231` | `_stream_response` 同步版 | 实际未被调用（仅在 async 版失败时作为 fallback） |
| 5 | `memory/memory_store.py:256` | `get_summary` | 被 `api.py:get_session_memory` 调用，但 `AgentMemoryManager` 从不调用，**形成"写但上层不读"** |
| 6 | `memory/memory_store.py:220` | `save_summary` | 写入 `conversation_summary`，但 `build_working_memory` **从不读** `conversation_summary` 表 |
| 7 | `tools/_search_cache.py:list_history` | `list_history` | 被 `record_search` 写入但 `api.py` memory stats 端点**从未调用 list_history** |

**死代码总计**：7 处

---

## B. 26 工具注册表（实际 30 个 @tool）

| # | Group | Tool Name | description | params | run 签名 | @with_owner | 注册 |
|---|-------|-----------|-------------|--------|----------|-------------|------|
| 1 | subscription | `list_subscriptions` | 列出当前用户订阅 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 2 | subscription | `add_subscription` | 新增订阅（需确认） | 8 字段 | `(_owner_id, name, type, ...)` | ✅ | ✅ |
| 3 | subscription | `update_subscription` | 修改订阅 | 8 字段 | `(subscription_id, _owner_id, **fields)` | ✅ | ✅ |
| 4 | subscription | `remove_subscription` | 删除订阅 | `subscription_id` | `(_owner_id, subscription_id)` | ✅ | ✅ |
| 5 | subscription | `parse_intent` | 自然语言→结构化意图 | `utterance` | `(_owner_id, utterance)` | ✅ | ✅ |
| 6 | scan | `trigger_scan` | 立即触发扫描（异步） | mode/subscription_ids/platforms | `(_owner_id, mode, ...)` | ✅ | ✅ |
| 7 | scan | `get_scan_status` | 查询扫描状态 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 8 | scan | `set_scan_interval` | 修改扫描频率 | `interval_min` | `(_owner_id, interval_min)` | ✅ | ✅ |
| 9 | scan | `pause_scheduler` | 暂停扫描 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 10 | scan | `resume_scheduler` | 恢复扫描 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 11 | scan | `get_next_run_time` | 下次扫描时间 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 12 | query | `search_alerts` | 检索预警/动态 | 7 过滤字段 | `(_owner_id, keyword, ...)` | ✅ | ✅ |
| 13 | query | `get_topic_detail` | 话题详情 | `topic_id` | `(_owner_id, topic_id)` | ✅ | ✅ |
| 14 | query | `get_subscription_stats` | 订阅统计 | `subscription_id, days` | `(_owner_id, subscription_id, days)` | ✅ | ✅ |
| 15 | push | `list_push_channels` | 列出通道 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 16 | push | `toggle_channel` | 开关通道 | `channel, enabled` | `(_owner_id, channel, enabled)` | ✅ | ✅ |
| 17 | push | `test_channel` | 测试通道 | `channel, message` | `(_owner_id, channel, message)` | ✅ | ✅ |
| 18 | push | `update_channel_config` | 更新通道配置 | `channel, config` | `(_owner_id, channel, config)` | ✅ | ✅ |
| 19 | model | `list_models` | 列出 6 角色模型 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 20 | model | `switch_model` | 切换模型 | 5 字段 | `(_owner_id, agent_role, ...)` | ✅ | ✅ |
| 21 | model | `test_model` | 测试模型 | `agent_role` | `(_owner_id, agent_role)` | ✅ | ✅ |
| 22 | search | `web_search` | **streamable** 全网搜索 | query/platforms/max_per_platform/time_range | `async (_owner_id, query, ...)` | ✅ | ✅ |
| 23 | search | `list_search_history` | 搜索历史 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 24 | search | `clear_search_cache` | 清空搜索历史 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 25 | system | `get_system_status` | 雷达状态 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 26 | system | `get_recent_alerts` | 高危预警 | `limit` | `(_owner_id, limit)` | ✅ | ✅ |
| 27 | system | `get_system_overview` | 综合快照 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 28 | system | `get_recent_activity` | 近 N 分钟活动 | `minutes` | `(_owner_id, minutes)` | ✅ | ✅ |
| 29 | system | `health_check` | 健康检查 | `null` | `(_owner_id) -> str` | ✅ | ✅ |
| 30 | ~~system~~ | ~~`trigger_background_crawl`~~ | ~~**废弃**旧工具~~ | ~~`keyword`~~ | ~~`async (keyword=None) -> str`~~ | ~~**❌ 无**~~ | ~~✅~~ **✅ 已移除（2026-06-11）** |

**@with_owner 缺失**：~~仅 `trigger_background_crawl`（system.py:80）一个工具~~ **✅ 已无缺失（P0 #6 修复后）**

---

## C. 调用链问题

### C1. ~~`trigger_background_crawl` 双重存在~~ ✅ 已解决（2026-06-11）

- ~~`agent_core.py:374-375`：
  ```python
  if function_name in ("trigger_scan", "trigger_background_crawl"):
  ```
  两个名字都在白名单中。~~
- ~~但 `system.py:80` 的函数名实际是 `_removed_trigger_background_crawl`，@tool 装饰器用 `name="trigger_background_crawl"` 指向它~~
- ~~新工具是 `scan.py:trigger_scan`，旧函数体仍可执行~~
- ~~**后果**：LLM 触发 `trigger_background_crawl` → 走非 per-user 旧路径（`from services.radar_service.main import radar_status, job, MONITOR_KEYWORDS`）→ **绕过 v2.2 tenant 隔离**~~
- ~~**修复**：从 `agent_core.py:375` 删除 `"trigger_background_crawl"`，并从 `system.py` 删除整个 `_removed_trigger_background_crawl` 函数~~

**修复实际落地（2026-06-11）**：
- `tools/system.py` 删除整个废弃函数 + `@tool(name="trigger_background_crawl")` 装饰器 + 整个 `2)` 节段头（65 行），同时清理 `asyncio` / `threading` / `traceback` / `time` 死 import。
- `agent_core.py:375` 改为单字符串 `function_name == "trigger_scan"`（不再用元组白名单）。
- `llm_gateway.py:54` `get_all_breakers()` 预热工具名从 `trigger_background_crawl` 改为 `trigger_scan`。
- 验证：`scripts/p0_6_trigger_bg_crawl_removal_test.py` 19/19 通过。

### C2. `memory_manager.write_from_conversation` 写入但 `build_working_memory` 不读

- 写入路径：
  - `write_from_conversation` → `store.save_summary()` → conversation_summary
  - `write_from_conversation` → `store.upsert_entity()` → entity_memory
  - `write_from_conversation` → `store.insert_fact()` → fact_memory
  - `write_from_conversation` → `store.upsert_pattern()` → pattern_memory
- 读出路径（`build_working_memory`）：
  - 读 entity_memory ✅
  - 读 fact_memory ✅
  - 读 pattern_memory ✅
  - **不读 conversation_summary** ❌
- **结果**：`conversation_summary` 表只有 `api.py:get_session_memory` 读它（且无 owner 验证），`AgentMemoryManager` 自身永不读

### C3. `tools/search.py:web_search` 异常静默

```python
try:
    async for partial in crawler_adapter.quick_crawl_stream(...):
        ...
except Exception:
    pass
```

crawler 异常被 `pass` 吞掉，返回空结果。**应记录 error 并返回失败 ToolResult**。

### C4. `DirectAdapter` async generator 取最后一项

- `search.py:127-131` 末尾 `yield ToolResult(...).to_json()` 返回 JSON 字符串
- 但 `DirectAdapter:72-73` 取 `parts[-1]` 当作最终结果
- 若 crawler 异常导致未 yield 到 ToolResult，`parts[-1]` 会是 progress dict 而非字符串
- 后续 `json.loads(result)` 失败

---

## D. 跨文件契约不一致 / Bug

### ~~D1. SQL 列索引错乱（`tools/system.py:341`）~~（已解决）

```python
SELECT post_id, title, platform, keyword, risk_level, create_time
FROM ai_results
...
"platform": r[0] if False else r[2],
```

- SQL 列顺序：`post_id(0) title(1) platform(2) keyword(3) risk_level(4) create_time(5)`
- 代码 `r[0] if False else r[2]`：因 `if False` 恒为 False，**结果取 `r[2]`**（=platform），**结果偶然正确**
- 但 `r[0]` 实际是 `post_id`，不是 `platform` — **逻辑完全错乱**
- `if False` 死分支

**修复（2026-06-11）**：`"platform": r[0] if False else r[2]` → `"platform": r[2]`（1 行修复）。
验证：grep 全项目（`if False` / `if True`）无其他死分支遗留。

### ~~D2. `memory/memory_store.py` owner_id 全缺失（严重）~~（已解决）

**修正**：agent_memory_db.py 和 memory_store.py:85-90 **v2.2 已做 ALTER TABLE 添加 owner_id 列**。真正问题是写入不传、读取不滤。本次 P0#2 修复：

**修复范围（4 个文件，279+/139- 行）**：
- `memory_store.py` 6 个方法（upsert_entity/insert_fact/upsert_pattern + get_frequent_entities/get_valid_facts/get_recent_patterns + get_summary/delete_session）签名加 `owner_id: str = ""` + `include_legacy: bool = True` 参数
- `memory_manager.py` build_working_memory / write_from_conversation / _analyze_and_write_patterns / delete_session 透传 owner_id
- `api.py` 2 个端点（get_session_memory / clear_session_memory）传 `current_user["id"]`
- `agent_core.py` build_working_memory 调用传 owner_id

**SQL 过滤模式**：
- 写入：`WHERE session_id=? AND owner_id=? AND ...` / INSERT 显式带 owner_id
- 读取（默认 include_legacy=True）：`WHERE session_id=? AND (owner_id=? OR owner_id='') AND ...`
- 读取（strict）：`WHERE session_id=? AND owner_id=? AND ...`
- 删除：返回实际删除行数，0 行 = session 不存在或不属于该 owner

**验证**：`scripts/p0_2_memory_isolation_test.py` 23/23 单元测试通过：
- 测试 1：A 写入、B 读不到（A 私域）✅
- 测试 2：legacy 数据 (owner_id='') 所有人可见（向后兼容）✅
- 测试 3：B 删 A 的 session 删不动（返回 0 行）✅
- 测试 4：同 session_id 不同 owner 物理隔离（entity/fact/pattern）✅
- 测试 5：A 删自己 → 删 A 自己的、不删 legacy、不影响 B ✅
- 测试 6：admin 模式 include_legacy=True 全删 ✅

**遗留问题（已发现但不在本 P0 修复）**：
- `agent_memory_db.py:63` `conversation_summary` 表的 UNIQUE 约束是 `UNIQUE(session_id)` 单列，**不是** `UNIQUE(session_id, owner_id)`
- 后果：当 A 和 B 用同一 session_id 写 summary 时，B 的 `INSERT OR REPLACE` 会覆盖 A 的整行（包括 owner_id 字段），A 的数据事实丢失
- 概率：UUID v4 碰撞概率极低（~10^-38），实际几乎不会发生
- 修复方案（独立 P0 候选）：重建 conversation_summary 表，改为 `UNIQUE(session_id, owner_id)` + save_summary 改应用层去重
- 建议处理：等本次 P0 列表完成后再开新 P0 修这个 schema 缺陷

**调用方完整性验证**（grep 全文）：
- `agent_core.py:289, 500` ✅
- `api.py:94, 114-117, 140` ✅
- `memory_manager.py:40, 53, 59, 98, 191-195, 203` ✅

### D3. `memory_manager._extract_entities` 依赖 jieba

- `memory_manager.py:147`：`import jieba.posseg as pseg`
- 若 jieba 不可用，**静默返回空列表 `[]`**，写入的 entities 永远为空
- 无 fallback 策略

### D4. `reflection_engine.py:48` 和 `diagnosis_engine.py:99` 硬编码模型

两处均用 `model="deepseek-chat"`，与主循环 `get_agent_config()` 动态获取不一致。

### D5. `agent_service/api.py` 无 admin 路由

CLAUDE.md 承诺"多用户 Admin 独立路由"，agent_service 无任何 admin 端点。

**已解决（2026-06-11 审查结论）**：Admin 路由实际部署在 `subscription_service/api.py`（AI 助手不需要自己的 admin 端点），含 `/api/admin/stats`、用户管理、配额管理、停用/角色修改等完整功能。CLAUDE.md 已不再承诺 agent_service 有独立 admin 路由，此为文档过时问题。

---

## E. Memory 闭环分析

### 写入表 vs 读出表

| 表 | 写入入口 | 读出入口 | owner_id 字段 | owner_id 过滤 |
|----|---------|---------|--------------|--------------|
| entity_memory | `upsert_entity` | `get_frequent_entities` (working memory) | ❌ 不写 | ❌ 不过滤 |
| fact_memory | `insert_fact` | `get_valid_facts` (working memory) | ❌ 不写 | ❌ 不过滤 |
| pattern_memory | `upsert_pattern` | `get_recent_patterns` (working memory) | ❌ 不写 | ❌ 不过滤 |
| conversation_summary | `save_summary` | `get_summary` (api.py) | ✅ 写入 | ❌ 不过滤 |

**问题**：
1. 三张表无 owner_id 字段 → schema 本身有问题
2. conversation_summary 有 owner_id 但不过滤 → 越权读取
3. `build_working_memory` 不读 conversation_summary → "写但上层不读"

### API 越权

`agent_service/api.py:113` `get_session_memory` 接受 `session_id`，**未验证 session 属于当前 owner** → 越权访问任意 session。

---

## F. v2 承诺落地情况

| 承诺 | 落地 | 备注 |
|------|------|------|
| 26 工具 | ✅ 30 个 @tool（含 1 废弃 + 3 空名/未装饰） | 实际有意义 26 个 |
| 全网搜索 | ✅ `web_search` + `_search_cache` | 异常静默 |
| 推送 Agent 决定 | ⚠️ push.py 有 4 工具但 RSS 被拒绝；`push_mode` 字段无业务实现 | 不完整 |
| 多用户 Admin 独立路由 | ❌ agent_service **无 admin 端点** | 未实现 |
| 4 类型订阅 | ✅ (在 subscription_service) | |
| RSS 通道 | ✅ (在 notifier) | 拉模式正确 |

---

## G. 必须修复清单

1. ~~`tools/system.py:341` — SQL 索引改为 `r[2]`，删除 `if False`~~ ✅ 已解决（2026-06-11）
2. ~~`memory/memory_store.py` — 三张表加 `owner_id` 字段 + 所有方法加过滤~~ ✅ 已解决（2026-06-11）
3. ~~`agent_core.py:375` — 删除 `"trigger_background_crawl"` 字符串~~ ✅ 已解决（2026-06-11，单字符串 `"trigger_scan"`）
4. ~~`tools/system.py:80` — 删除整个 `_removed_trigger_background_crawl` 函数（含 @tool 装饰器）~~ ✅ 已解决（2026-06-11，删除 65 行）
5. ~~`api.py:113` — `get_session_memory` 加 owner 验证~~ ✅ 已解决（2026-06-11）
6. `tools/subscription.py:13` — 删除 `import json`
7. `agent_core.py:304` — `medi_count` 移到循环外
8. `search.py` — `web_search` 异常改为记录 + 返回失败 ToolResult
9. `reflection_engine.py:48` + `diagnosis_engine.py:99` — 改用 `get_agent_config()` 动态获取
10. `memory_manager.py` — jieba 缺失时 fallback 策略
