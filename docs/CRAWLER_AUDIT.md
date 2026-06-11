# 爬虫层多用户隔离审计 (WS6-C1)

**日期**: 2026-06-11
**审计对象**: `backend/services/crawler_service/` + `radar_service/main.py` 中的爬虫调用点
**结论**: **爬虫层当前完全没有多用户隔离** —— 必须作为独立专项处理

---

## 🔴 致命发现

### F1. 许可证风险（商业化阻塞）

**文件**: `backend/services/crawler_service/main.py:1-8`

```
This file is part of MediaCrawler project.
Repository: https://github.com/NanmiCoder/MediaCrawler
Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
```

爬虫目录是 fork 的 MediaCrawler，许可证为 **NON-COMMERCIAL LEARNING LICENSE1.1** —— **禁止商业用途**。MediaRadar 商业化上线前必须：
1. 联系作者获取商用授权
2. 或自研替换
3. 或换 AGPL/MIT 等可商用项目

**优先级**: P0（影响整个产品能否上线）

### F2. 爬虫结果无 owner_id 归属

**文件**: `backend/services/crawler_service/database/models.py`

爬虫内部 `user_id` 列全部是**被爬的社交平台用户**（微博UID/抖音UID等），**不是 MediaRadar 租户**。整个 `crawler_service` 数据库完全没有任何 MediaRadar tenant 标识。

后果：扫描结果进入 MediaRadar SQLite 时如何归属到 owner_id，**没有保证**。

### F3. 触发链路全局化（严重跨用户串数据）

**文件**: `backend/services/radar_service/main.py:134-165`

```python
def run_crawler_for_platform(platform):
    keywords_str = ",".join(MONITOR_KEYWORDS)  # ← 全局关键词
    subprocess.run(
        [VENV_PYTHON, "main.py", "--platform", platform,
         "--type", "search", "--save_data_option", "sqlite",
         "--keywords", keywords_str],
        cwd=CRAWLER_DIR, timeout=600
    )
```

**问题**：
- `MONITOR_KEYWORDS` 是全局变量，**所有用户的关键词被合并后传给爬虫**
- 单用户触发扫描 → 爬虫按全部用户的关键词一起抓 → 抓回的数据进入 MediaRadar SQLite 后**只能随机归属或全部归触发者**
- 即便在 SQLite 里按 owner_id 过滤，A 触发一次抓到的可能是 B 想要的词

**优先级**: P0

### F4. 爬虫是独立进程，无 owner_id 透传

`subprocess.run([VENV_PYTHON, "main.py", ...])` 不传 owner_id。爬虫自身也没有"为某个 owner_id 服务"的概念。

要修必须：
1. 在 CLI 参数加 `--owner_id`（爬虫需改）
2. 爬虫结果落 SQLite 时带 owner_id（爬虫需改）
3. MediaRadar 拉取时按 owner_id 过滤（db_manager 已有 `get_unprocessed_posts`，需加 owner_id 透传）

### F5. `get_unprocessed_posts` 无 owner_id 参数

**文件**: `backend/services/radar_service/db_manager.py:344-349`

```python
def get_unprocessed_posts(crawler_db_path, platform):
    if not os.path.exists(crawler_db_path):
        ...
    conn = get_db_connection(db_path=crawler_db_path)
    # 后续 SQL 无 owner_id 过滤
```

即便爬虫能写 owner_id，这里也不读。**链路断在中间**。

### F6. 全局串行爬虫锁（性能 + 公平性）

**文件**: `backend/services/radar_service/main.py:228-235`

```python
results = await asyncio.gather(
    run_crawler_for_platform_async(p) for p in MONITOR_PLATFORMS
)
```

`MONITOR_PLATFORMS` 也是全局变量。多用户并行触发时，asyncio.gather 并发跑 N 个爬虫子进程，会：
- 互相抢 Cookie / 浏览器实例（爬虫用 Playwright/Selenium）
- 互相抢 SQLite 写入锁
- 单个爬虫 timeout 600s 会阻塞其他用户

---

## ⚠️ 中危

### M-C1. `vision_agent.py` 引用爬虫文件系统路径

**文件**: `backend/services/radar_service/vision_agent.py:62-65`

```python
local_path = os.path.join(BASE_DIR, "services", "crawler_service", "data",
                          dir_name, "images", str(post_id), "0.jpg")
```

爬虫产物路径耦合在 radar_service。如果未来爬虫目录重构或移到独立容器，此路径会失效。无 owner_id 子目录隔离（多人扫描同一平台的图片混在一个目录里）。

### M-C2. Cookie / 账号资源竞争

爬虫用 Playwright + 平台 Cookie 登录。Cookie 是单租户级别（一个微博账号），多用户共享同一套爬虫账号 = 全部用户都被微博关联同一身份。爬虫被风控时所有用户受影响。

---

## ✅ 仍可用的部分

| 组件 | 说明 |
|------|------|
| `crawler_service/media_platform/` | 7 平台爬虫实现完整 |
| `crawler_service/database/` | MySQL/SQLAlchemy 模型（需要重写为 SQLite + owner_id） |
| `radar_service/main.py:run_crawler_for_platform_async` | 异步 subprocess 框架，可保留 |

---

## 修复路线建议（不在本轮范围）

### Phase A - 解耦（短期）
1. **每个 owner_id 独立爬虫 SQLite 文件**：`crawler_data/<owner_id>/<platform>.sqlite`
2. 爬虫子进程加 `--owner_id` 参数，输出到该 owner_id 目录
3. `get_unprocessed_posts(crawler_db_path, platform, owner_id)` 加 owner_id 参数
4. `MONITOR_KEYWORDS` 拆为按 owner_id 的字典，触发时按 owner_id 取自己的

### Phase B - 重构（中期）
1. 替换 MediaCrawler 为自研 / 合规替代品（F1 阻塞项先解决）
2. 爬虫账号池化（每用户独立 Cookie / 用平台 API）
3. 拆爬虫到独立微服务 + 队列

### Phase C - 商业化（长期）
1. 解决许可证（F1）
2. 容器化爬虫 worker
3. 接入任务队列（Celery / RQ）

---

## 本轮处理决定

**爬虫层整体重构超出 WS6 范围**，但记录**两个立即可做的最小补丁**：
1. ✅ `get_unprocessed_posts` 加 owner_id 参数（占位，不改行为，避免破坏当前流程）
2. ✅ `MONITOR_KEYWORDS` 拆分警告日志，提醒单用户触发的扫描混入全局关键词

不修爬虫子进程本身（修改爬虫会引入许可证合规风险）。