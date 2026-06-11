'use client';

/**
 * useAgentStream — 流式 SSE → React state
 *
 * 核心设计：
 *   - 每个 SSE 事件调用 applyEvent → setAssistant
 *   - 每次事件后 await setTimeout(0) 让出事件循环，React 得以渲染
 *   - 流结束后 finally 块确保 done 状态写入
 */
import { useCallback, useRef, useState } from 'react';
import { getToken } from '@/lib/auth-client';
import { parseSSE } from './sse-parser';
import type {
  AssistantMessage,
  ParsedSSEEvent,
  SSEToolCall,
  SSEToolResult,
  ToolCallBlock,
  UICard,
} from './sse-types';

interface SendOptions {
  sessionId?: string | null;
  baseUrl?: string;
}

interface UseAgentStreamResult {
  assistant: AssistantMessage | null;
  isStreaming: boolean;
  error: string | null;
  send: (messages: { role: 'user' | 'assistant'; content: string }[], options?: SendOptions) => Promise<void>;
  cancel: () => void;
  reset: () => void;
}

const EMPTY_ASSISTANT: AssistantMessage = {
  role: 'assistant',
  text: '',
  toolCalls: [],
  cards: [],
  done: false,
};

export function useAgentStream(): UseAgentStreamResult {
  const [assistant, setAssistant] = useState<AssistantMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setAssistant(null);
    setError(null);
    setIsStreaming(false);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const send = useCallback(
    async (
      messages: { role: 'user' | 'assistant'; content: string }[],
      options: SendOptions = {},
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setAssistant({ ...EMPTY_ASSISTANT });
      setError(null);
      setIsStreaming(true);

      const token = getToken();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const chatUrl = options.baseUrl
        ? `${options.baseUrl}/api/agent/chat`
        : '/api/agent/chat';

      let res: Response;
      try {
        res = await fetch(chatUrl, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            messages,
            session_id: options.sessionId ?? null,
          }),
          signal: controller.signal,
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : '请求失败');
        setIsStreaming(false);
        return;
      }

      if (!res.ok || !res.body) {
        const txt = await res.text().catch(() => '');
        setError(`HTTP ${res.status}${txt ? `: ${txt.slice(0, 120)}` : ''}`);
        setIsStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      try {
        for await (const ev of parseSSE(reader)) {
          if (controller.signal.aborted) break;
          applyEvent(ev);
          // 每事件让出，React 得以渲染当前累积的文本
          await new Promise((r) => setTimeout(r, 0));
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          // 用户取消
        } else {
          setError(e instanceof Error ? e.message : '流解析失败');
        }
      } finally {
        setIsStreaming(false);
        setAssistant((prev) => {
          if (!prev) return { ...EMPTY_ASSISTANT, done: true };
          if (prev.done) return prev;
          return { ...prev, done: true };
        });
      }
    },
    [], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // applyEvent: 把单个 SSE 事件 fold 到 assistant state
  const applyEvent = useCallback((ev: ParsedSSEEvent) => {
    setAssistant((prev) => {
      const next: AssistantMessage = prev ? { ...prev } : { ...EMPTY_ASSISTANT };

      switch (ev.event) {
        case 'text': {
          next.text += ev.data;
          break;
        }
        case 'tool_call': {
          const tc = ev.data as SSEToolCall;
          const block: ToolCallBlock = {
            call_id: tc.call_id,
            tool: tc.tool,
            args: tc.args,
            status: 'pending',
          };
          next.toolCalls = upsertBlock(next.toolCalls, block);
          break;
        }
        case 'tool_progress': {
          const tp = ev.data;
          next.toolCalls = next.toolCalls.map((b) =>
            b.call_id === tp.call_id ? { ...b, status: 'streaming' as const } : b,
          );
          break;
        }
        case 'tool_result': {
          const tr = ev.data as SSEToolResult;
          next.toolCalls = next.toolCalls.map((b) =>
            b.call_id === tr.call_id
              ? { ...b, result: tr, status: (tr.success ? 'success' : 'error') as 'success' | 'error' }
              : b,
          );
          if (tr.ui && tr.ui.type) {
            next.cards = [
              ...next.cards.filter((c) => c.key !== tr.call_id),
              {
                key: tr.call_id,
                ui: tr.ui,
                data: tr.data,
                tool: next.toolCalls.find((b) => b.call_id === tr.call_id)?.tool ?? '',
              },
            ];
          }
          break;
        }
        case 'error': {
          if (!ev.data.call_id) {
            next.error = ev.data.message;
          } else {
            next.toolCalls = next.toolCalls.map((b) =>
              b.call_id === ev.data.call_id ? { ...b, status: 'error' as const } : b,
            );
          }
          break;
        }
        case 'done': {
          next.done = true;
          break;
        }
      }
      return next;
    });
  }, []);

  return { assistant, isStreaming, error, send, cancel, reset };
}

function upsertBlock(list: ToolCallBlock[], block: ToolCallBlock): ToolCallBlock[] {
  const i = list.findIndex((b) => b.call_id === block.call_id);
  if (i === -1) return [...list, block];
  const next = list.slice();
  next[i] = { ...next[i], ...block };
  return next;
}
