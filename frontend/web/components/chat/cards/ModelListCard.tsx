'use client';

/**
 * ModelListCard —— LLM 模型角色列表
 *
 * data: { roles: [{ role, model, provider, has_api_key, fallback_to_default }] }
 */
import { Card } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface RoleItem {
  role?: string;
  model?: string;
  provider?: string;
  has_api_key?: boolean;
  fallback_to_default?: boolean;
}

const ROLE_LABEL: Record<string, string> = {
  DEFAULT: '默认模型',
  ANALYST: '分析员',
  REVIEWER: '复核员',
  EMBEDDING: '向量引擎',
  VISION: '视觉引擎',
  AGENT: 'AI 助手',
};

export function ModelListCard({ card }: CardProps) {
  const raw = (card.ui.data ?? card.data ?? {}) as { roles?: RoleItem[] };
  const roles = raw.roles ?? [];

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        模型角色
      </div>
      <ul className="divide-y divide-border">
        {roles.map((it, i) => (
          <li key={it.role ?? i} className="flex items-center gap-3 px-3 py-2.5">
            <Sparkles
              className={cn(
                'h-3.5 w-3.5 shrink-0',
                it.has_api_key ? 'text-primary' : 'text-muted-foreground',
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                {ROLE_LABEL[it.role ?? ''] ?? it.role}
              </div>
              <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                {it.model ?? '(未配置)'}
                {it.provider && <> · {it.provider}</>}
              </div>
            </div>
            {it.fallback_to_default && (
              <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                回退默认
              </span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
