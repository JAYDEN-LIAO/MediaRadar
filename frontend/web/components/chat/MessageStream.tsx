'use client';

/**
 * MessageStream —— 渲染流式助手消息。
 *
 * 内部并不拥有 state，由父组件传入 AssistantMessage（来自 useAgentStream）。
 * 历史消息可以直接复用本组件渲染：传入 done=true 的 message 即可。
 *
 * 布局：
 *   ┌─ Bot 头像 ─┬─ 文本(streaming 可带光标) ─────────────
 *               ├─ ToolCallChip + ToolCallChip ...
 *               └─ 卡片 (registry 渲染)
 */
import { Bot, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { ToolCallChip } from './ToolCallChip';
import { renderCard } from './cards/registry';
import type { AssistantMessage } from './sse-types';

interface Props {
  message: AssistantMessage;
  streaming?: boolean;
}

export function MessageStream({ message, streaming = false }: Props) {
  const hasText = message.text.length > 0;
  const hasTools = message.toolCalls.length > 0;
  const hasCards = message.cards.length > 0;
  const showCursor = streaming && !message.done;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-4 flex gap-3"
    >
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted text-foreground">
        <Bot className="h-4 w-4" />
      </div>
      <div className="min-w-0 max-w-[80%] flex-1">
        {/* 文本 */}
        {hasText && (
          <div className="rounded-2xl bg-muted/60 px-4 py-2.5 text-sm leading-relaxed text-foreground">
            <span className="whitespace-pre-wrap break-words">
              {message.text}
              {showCursor && <span className="ml-0.5 animate-pulse">▍</span>}
            </span>
          </div>
        )}
        {!hasText && showCursor && (
          <div className="rounded-2xl bg-muted/60 px-4 py-2.5 text-sm">
            <span className="animate-pulse text-muted-foreground">思考中…</span>
          </div>
        )}

        {/* 工具调用 chip */}
        {hasTools && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.toolCalls.map((tc) => (
              <ToolCallChip key={tc.call_id} block={tc} />
            ))}
          </div>
        )}

        {/* 卡片 */}
        {hasCards && (
          <div className="mt-2">
            {message.cards.map((c) => (
              <div key={c.key}>{renderCard(c)}</div>
            ))}
          </div>
        )}

        {/* 错误 */}
        {message.error && (
          <div className="mt-2 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{message.error}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
