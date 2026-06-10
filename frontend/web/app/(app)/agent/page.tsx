'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User as UserIcon, Plus, MessageSquare } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { agentApi, type AgentMessage, type AgentSession } from '@/lib/api';

const SUGGESTIONS = [
  '今天有哪些高风险舆情？',
  '帮我分析最近 24 小时品牌口碑趋势',
  '对比比亚迪和竞品的舆情数据',
  '触发一次后台全网扫描',
];

export default function AgentPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([
    { role: 'assistant', content: '你好！我是 MediaRadar 智能助手，可以帮你查询舆情数据、触发扫描、分析趋势。请问需要什么帮助？' },
  ]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const sessionsQuery = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => agentApi.memory(),
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  // 真实 SSE 流式对话
  const sendMessage = async (text: string) => {
    if (!text.trim() || streaming) return;
    const userMsg: AgentMessage = { role: 'user', content: text };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setStreaming(true);

    const assistantMsg: AgentMessage = { role: 'assistant', content: '' };
    setMessages((m) => [...m, assistantMsg]);

    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
      const res = await fetch(`${base}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages, userMsg],
          session_id: sessionId,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`API ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留未完成行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6);
            if (chunk === '[DONE]') break;
            setMessages((m) => {
              const next = [...m];
              next[next.length - 1] = { ...next[next.length - 1], content: (next[next.length - 1].content || '') + chunk };
              return next;
            });
          }
        }
      }
    } catch (e) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = { role: 'assistant', content: `抱歉，请求失败: ${e instanceof Error ? e.message : '未知错误'}` };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid h-[calc(100vh-200px)] grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
        {/* Sessions list */}
        <Card className="hidden flex-col overflow-hidden lg:flex">
          <div className="flex items-center justify-between border-b border-border p-3">
            <span className="text-sm font-semibold">会话列表</span>
            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setSessionId(null)}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {(() => {
              if (sessionsQuery.isLoading) {
                return Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="mb-2 h-12 w-full" />
                ));
              }
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
              return <p className="p-3 text-center text-xs text-muted-foreground">暂无历史会话</p>;
            })()}
          </div>
        </Card>

        {/* Chat panel */}
        <Card className="flex flex-col overflow-hidden">
          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
            {messages.length === 1 && (
              <div className="grid h-full place-items-center">
                <div className="w-full max-w-lg text-center">
                  <p className="mb-4 text-sm text-muted-foreground/60">快捷提问</p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <Button key={s} variant="outline" size="sm" onClick={() => sendMessage(s)} className="text-xs">
                        {s}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <AnimatePresence initial={false}>
              {messages.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn('mb-4 flex gap-3', m.role === 'user' ? 'justify-end' : 'justify-start')}
                >
                  {m.role === 'assistant' && (
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted text-foreground">
                      <Bot className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={cn(
                      'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                      m.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted/60 text-foreground',
                    )}
                  >
                    {m.content || (streaming && i === messages.length - 1 ? <span className="animate-pulse">▍</span> : '')}
                  </div>
                  {m.role === 'user' && (
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted">
                      <UserIcon className="h-4 w-4" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {/* Input */}
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
                placeholder="向 AI 助手提问…"
                disabled={streaming}
                className="flex-1"
              />
              <Button type="submit" size="icon" disabled={streaming || !input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}
