'use client';

/**
 * SubscriptionListCard —— 订阅列表卡片
 *
 * 后端 data 形态参考 services/agent_service/tools/subscription.py 的 list_subscriptions：
 *   { items: [{ id, type, query, status, created_at, ... }], total }
 */
import { Card } from '@/components/ui/card';
import { Bell, BellOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface SubItem {
  id?: string | number;
  type?: string;
  query?: string;
  name?: string;
  status?: string;
  created_at?: string;
}

const TYPE_LABEL: Record<string, string> = {
  brand: '品牌',
  topic: '话题',
  industry: '行业',
  custom: '自定义',
};

export function SubscriptionListCard({ card }: CardProps) {
  const raw = (card.ui.data ?? card.data ?? {}) as { items?: SubItem[]; total?: number };
  const items = raw.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="my-2 p-4 text-center text-sm text-muted-foreground">
        你还没有订阅，告诉我你感兴趣的关键词即可创建。
      </Card>
    );
  }

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        订阅清单 · {raw.total ?? items.length} 条
      </div>
      <ul className="divide-y divide-border">
        {items.map((it, i) => {
          const active = (it.status ?? 'active') === 'active';
          return (
            <li key={it.id ?? i} className="flex items-center gap-3 px-3 py-2.5">
              <div
                className={cn(
                  'grid h-7 w-7 shrink-0 place-items-center rounded-full',
                  active ? 'bg-emerald-500/15 text-emerald-600' : 'bg-muted text-muted-foreground',
                )}
              >
                {active ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {it.name ?? it.query ?? '(未命名)'}
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {TYPE_LABEL[it.type ?? ''] ?? it.type ?? '订阅'}
                  {it.created_at && <> · {it.created_at.slice(0, 10)}</>}
                </div>
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium',
                  active
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {active ? '生效中' : '已暂停'}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
