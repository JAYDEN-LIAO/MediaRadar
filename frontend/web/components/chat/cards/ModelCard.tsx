'use client';

/** ModelCard —— 单角色模型配置结果（switch_model） */
import { Card } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

const ROLE_LABEL: Record<string, string> = {
  DEFAULT: '默认模型', ANALYST: '分析员', REVIEWER: '复核员',
  EMBEDDING: '向量引擎', VISION: '视觉引擎', AGENT: 'AI 助手',
};

export function ModelCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    agent_role?: string;
    model?: string;
    provider?: string;
    has_api_key?: boolean;
  };
  const role = d.agent_role ?? '';

  return (
    <Card className="my-2 p-3">
      <div className="flex items-center gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {ROLE_LABEL[role] ?? role}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {d.model ?? '(未配置)'}
            {d.provider && <> · {d.provider}</>}
          </div>
        </div>
        <span
          className={cn(
            'shrink-0 rounded-full px-2 py-0.5 text-[10px]',
            d.has_api_key
              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
              : 'bg-muted text-muted-foreground',
          )}
        >
          {d.has_api_key ? '已配 Key' : '未配 Key'}
        </span>
      </div>
    </Card>
  );
}
