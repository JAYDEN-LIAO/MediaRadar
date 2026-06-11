'use client';

/**
 * Agent 页面 —— 接入 P2 SSE 多事件协议。
 *
 * 布局：
 *   [会话列表 260] [Chat 主区 1fr] [右侧看板 280]
 *
 * 流式：useAgentStream + MessageStream 渲染 text / tool_call / tool_result 卡片。
 */
import { useState, useRef, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, User as UserIcon, Plus, MessageSquare, X } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { agentApi, type AgentSession } from '@/lib/api';
import { useAgentStream } from '@/components/chat/useAgentStream';
import { MessageStream } from '@/components/chat/MessageStream';
import { RightDashboard } from '@/components/chat/RightDashboard';
import { LoginBrief } from '@/components/chat/LoginBrief';
import type { AssistantMessage } from '@/components/chat/sse-types';

type UIMessage =
  | { kind: 'user'; content: string }
  | { kind: 'assistant'; data: AssistantMessage };

const SUGGESTIONS = [
  '展示我的订阅清单',
  '帮我分析最近 24 小时品牌口碑趋势',
  '看看今天的高危话题',
  '触发一次后台全网扫描',
];

const WELCOME: AssistantMessage = {
  role: 'assistant',
  text: '你好！我是 MediaRadar 智能助手。可以帮你管理订阅、查询舆情、调度爬虫、检查推送通道。直接说出你的需求即可。',
  toolCalls: [],
  cards: [],
  done: true,
};

export default function AgentPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<UIMessage[]>([
    { kind: 'assistant', data: WELCOME },
  ]);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const { assistant, isStreaming, error, send, cancel } = useAgentStream();

  const sessionsQuery = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => agentApi.memory(),
  });

  // 滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [history, assistant?.text, assistant?.toolCalls.length, assistant?.cards.length]);

  // 当 assistant 进入 done 状态，把它持久化进 history
  useEffect(() => {
    if (assistant?.done && !isStreaming) {
      setHistory((h) => {
        // 防止重复 push（StrictMode 双调用兜底）
        const last = h[h.length - 1];
        if (
          last &&
          last.kind === 'assistant' &&
          last.data === assistant
        ) {
          return h;
        }
        return [...h, { kind: 'assistant', data: assistant }];
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assistant?.done, isStreaming]);

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    setHistory((h) => [...h, { kind: 'user', content: trimmed }]);
    setInput('');

    // 把 history 拍平成 openai 风格 messages
    const flatMessages = [
      ...history.flatMap<{ role: 'user' | 'assistant'; content: string }>((m) =>
        m.kind === 'user'
          ? [{ role: 'user' as const, content: m.content }]
          : m.data.text
            ? [{ role: 'assistant' as const, content: m.data.text }]
            : [],
      ),
      { role: 'user' as const, content: trimmed },
    ];

    await send(flatMessages, { sessionId });
  };

  const startNewSession = () => {
    cancel();
    setSessionId(null);
    setHistory([{ kind: 'assistant', data: WELCOME }]);
  };

  const showSuggestions = useMemo(
    () => history.length === 1 && !isStreaming && !assistant,
    [history.length, isStreaming, assistant],
  );

  return (
    <div className="grid h-[calc(100vh-160px)] grid-cols-1 gap-3 lg:grid-cols-[240px_1fr_280px]">
      {/* —— 左：会话列表 —— */}
      <Card className="hidden flex-col overflow-hidden lg:flex">
        <div className="flex items-center justify-between border-b border-border p-3">
          <span className="text-sm font-semibold">会话</span>
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            onClick={startNewSession}
            title="新建会话"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessionsQuery.isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="mb-2 h-12 w-full" />
            ))
          ) : (() => {
            const sessions = sessionsQuery.data?.sessions;
            if (Array.isArray(sessions) && sessions.length > 0) {
              return sessions.map((s: AgentSession) => (
                <button
                  key={s.session_id}
                  onClick={() => setSessionId(s.session_id)}
                  className={cn(
                    'mb-1 flex w-full items-center gap-2 rounded-lg p-2 text-left text-sm transition-colors hover:bg-accent',
                    sessionId === s.session_id && 'bg-primary/10 text-primary',
                  )}
                >
                  <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate text-xs">{s.title}</span>
                </button>
              ));
            }
            return (
              <p className="p-3 text-center text-xs text-muted-foreground">
                暂无历史会话
              </p>
            );
          })()}
        </div>
      </Card>

      {/* —— 中：聊天主区 —— */}
      <Card className="flex flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
          {/* 历史消息 */}
          <AnimatePresence initial={false}>
            {history.map((m, i) => {
              if (m.kind === 'user') {
                return (
                  <motion.div
                    key={`u-${i}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-4 flex justify-end gap-3"
                  >
                    <div className="max-w-[80%] rounded-2xl bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
                      {m.content}
                    </div>
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted">
                      <UserIcon className="h-4 w-4" />
                    </div>
                  </motion.div>
                );
              }
              return (
                <MessageStream
                  key={`a-${i}`}
                  message={m.data}
                  streaming={false}
                />
              );
            })}
          </AnimatePresence>

          {/* 当前流式 assistant —— done 后会进 history，未 done 时这里展示 */}
          {assistant && !assistant.done && (
            <MessageStream message={assistant} streaming={true} />
          )}

          {/* 全局错误 */}
          {error && (
            <div className="my-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
              {error}
            </div>
          )}

          {/* 快捷提问 + 登录简报 */}
          {showSuggestions && (
            <div className="flex flex-col items-center">
              {/* 数据简报 */}
              <div className="w-full max-w-lg">
                <LoginBrief onAction={sendMessage} />
              </div>
              {/* 快捷按钮 */}
              <div className="mt-6 w-full max-w-lg text-center">
                <p className="mb-3 text-sm text-muted-foreground/60">
                  快速提问
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      size="sm"
                      onClick={() => sendMessage(s)}
                      className="text-xs"
                    >
                      {s}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 输入框 */}
        <div className="border-t border-border bg-background/40 p-4 backdrop-blur">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="flex items-center gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                isStreaming ? 'AI 正在回复…' : '向 AI 助手提问…'
              }
              disabled={isStreaming}
              className="flex-1"
            />
            {isStreaming ? (
              <Button
                type="button"
                size="icon"
                variant="outline"
                onClick={cancel}
                title="中止"
              >
                <X className="h-4 w-4" />
              </Button>
            ) : (
              <Button type="submit" size="icon" disabled={!input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            )}
          </form>
        </div>
      </Card>

      {/* —— 右：看板 —— */}
      <div className="hidden lg:block">
        <RightDashboard onQuickAction={sendMessage} />
      </div>
    </div>
  );
}
