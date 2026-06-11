/**
 * SSE 字节流解析器（P2 协议）
 *
 * 输入：ReadableStreamDefaultReader<Uint8Array>
 * 输出：异步迭代器，yield ParsedSSEEvent
 *
 * 实现要点：
 *   - 按行切分（\n、\r、\r\n 都支持）
 *   - 空行代表一个事件结束
 *   - data: 后面是 JSON 字符串（text 事件也是 JSON-encoded 字符串）
 *   - event: 后面是事件名
 *   - done 事件的 data 字段可能为空
 */
import type { ParsedSSEEvent, SSEEventName } from './sse-types';

const VALID_EVENTS: ReadonlySet<string> = new Set([
  'text',
  'tool_call',
  'tool_progress',
  'tool_result',
  'error',
  'done',
]);

export async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  decoder: TextDecoder = new TextDecoder('utf-8'),
): AsyncGenerator<ParsedSSEEvent, void, void> {
  let buffer = '';
  let currentEvent: SSEEventName | null = null;
  const dataLines: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      // 流结束：处理残留 buffer
      const tail = buffer + decoder.decode();
      const finalLines = tail.split(/\r?\n/);
      for (const line of finalLines) {
        _processLine(line);
      }
      const finalEvent = _flush();
      if (finalEvent) yield finalEvent;
      return;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? ''; // 保留未完成行

    for (const line of lines) {
      const ev = _processLine(line);
      if (ev) {
        yield ev;
        // 事件结束后重置状态
        currentEvent = null;
        dataLines.length = 0;
      }
    }
  }

  // ─── 内部函数：直接访问闭包变量 ───

  function _processLine(line: string): ParsedSSEEvent | null {
    // 空行 = 事件边界 → flush 当前事件
    if (line === '') {
      return _flush();
    }
    // 注释行
    if (line.startsWith(':')) return null;

    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) return null;

    const field = line.slice(0, colonIdx);
    // SSE 规范：field: value（冒号后第一个空格去掉）
    const value =
      line.length > colonIdx + 1 && line[colonIdx + 1] === ' '
        ? line.slice(colonIdx + 2)
        : line.slice(colonIdx + 1);

    if (field === 'event') {
      currentEvent = VALID_EVENTS.has(value) ? (value as SSEEventName) : null;
    } else if (field === 'data') {
      dataLines.push(value);
    }
    // id / retry 等字段暂不消费
    return null;
  }

  function _flush(): ParsedSSEEvent | null {
    if (currentEvent === null) return null;

    const raw = dataLines.join('\n');

    if (currentEvent === 'done') {
      return { event: 'done', data: '' };
    }
    if (currentEvent === 'text') {
      try {
        return { event: 'text', data: JSON.parse(raw) as string };
      } catch {
        return { event: 'text', data: raw };
      }
    }
    // tool_call / tool_result / error / tool_progress
    try {
      return { event: currentEvent, data: JSON.parse(raw) } as ParsedSSEEvent;
    } catch {
      return null;
    }
  }
}
