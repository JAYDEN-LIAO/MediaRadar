# 问题记录：Windows SelectorEventLoop 导致子进程无法启动

## 现象

Agent 调用 `web_search` 工具时，后端日志报错：

```
[CrawlerAdapter] wb 爬虫异常 [NotImplementedError]: NotImplementedError()
```

爬虫子进程完全无法启动。同时期其他功能（定时扫描、Chat 对话）正常。

## 影响范围

| 功能 | 是否受影响 |
|------|-----------|
| Agent `web_search`（全网搜索）| 是 — 完全无法启动爬虫 |
| 定时扫描（scheduler）| 否 — 调度器在独立线程创建新事件循环 |
| Agent 工具调用（除搜索外）| 否 — 不涉及子进程 |
| Chat 普通对话 | 否 |

## 根因分析

### 直接原因

uvicorn 主进程运行在 **`_WindowsSelectorEventLoop`** 上。该事件循环的 `create_subprocess_exec()` 方法未实现，直接 `raise NotImplementedError`。

验证方式：

```python
import asyncio
loop = asyncio.get_running_loop()
print(type(loop).__name__)  # 输出: _WindowsSelectorEventLoop
```

### 底层原理

Windows Python 有两种事件循环：

| | SelectorEventLoop | ProactorEventLoop |
|---|---|---|
| 底层技术 | `select()` | IOCP（I/O Completion Ports） |
| 监控对象 | 仅 socket 句柄 | socket + 管道 + 进程句柄 |
| 子进程支持 | ❌ `NotImplementedError` | ✅ |
| Python 3.8+ 默认 | 否 | 是 |

子进程的 stdin/stdout/stderr 在 Windows 内部由**命名管道**实现。`select()` 是 Unix 的 API，Windows 移植版只支持监控 socket 句柄，无法监控管道句柄。IOCP 是 Windows 原生异步 I/O 接口，支持任意 Overlapped I/O 句柄，包括管道。

因此 `asyncio.create_subprocess_exec()` → 需要管道 → 需要 ProactorEventLoop → SelectorEventLoop 上直接抛异常。

### 为什么 SelectorEventLoop 出现了

uvicorn `reload=True` 模式下，子进程在启动早期，`asyncio` 的 event loop policy 尚未被显式初始化，拿到的是"未设定"状态。Python 3.11 在这种状态下可能回退到 `_WindowsSelectorEventLoop`（具体行为取决于 `asyncio` 内部初始化时序）。

### 为什么定时扫描不受影响

`scheduler.py` 中的 `_run_scan()` 在独立线程中执行：

```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
```

`new_event_loop()` 调用时会正确使用 `WindowsProactorEventLoopPolicy` 创建 ProactorEventLoop，因此测试进程能正常启动。而 API 请求处理走在 uvicorn 主事件循环上，未受保护。

### 为什么"上午还能用"

v2.2 早期迭代中，`web_search` 是占位实现：

```python
# P1 占位 — 不触发任何子进程
return ToolResult(success=True, data={"items": [], "total": 0, "status": "not_implemented"}, ...)
```

对接真实的 `search_lib/crawler_adapter.py` 之后，才真正调用 `asyncio.create_subprocess_exec()`，问题才暴露。

## 修复

在 `backend/gateway/main.py` 最顶部（所有 import 之前）强制设置 Windows ProactorEventLoop：

```python
import asyncio as _asyncio_init
import sys as _sys_init
if _sys_init.platform == "win32":
    _asyncio_init.set_event_loop_policy(_asyncio_init.WindowsProactorEventLoopPolicy())
```

这确保 uvicorn 创建事件循环时，policy 已是 ProactorEventLoop，所有 `asyncio.new_event_loop()` 调用都获得支持子进程的事件循环。

### 风险评估

零风险。Python 3.8+ 在 Windows 上已将 ProactorEventLoop 设为默认值。此修复只是确保这个默认值在所有代码路径上都生效，不是"切换"事件循环类型。

| 能力 | Selector | Proactor |
|------|----------|----------|
| Socket I/O | ✅ | ✅ |
| 子进程 | ❌ | ✅ |
| 管道 | ❌ | ✅ |

## 复现方法

1. Windows 环境下启动后端
2. 通过 Agent Chat 发送："搜索一下微博平台关于华为手机的最新消息"
3. 观察后端日志出现 `NotImplementedError`

## 修复验证

1. 重启后端后发送相同请求
2. 后端日志应出现 `loop=ProactorEventLoop`
3. 爬虫正常启动并返回结果
4. Agent 收到结果后生成回复

## 日期

2026-06-11
