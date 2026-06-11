'use client';

/**
 * TopicListCard —— 话题/舆情列表卡片
 *
 * data: { items: [{ topic_id, topic_name, risk_class, post_count, last_seen, ... }] }
 */
import { Card } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface TopicItem {
  topic_id?: string;
  topic_name?: string;
  keyword?: string;
  risk_class?: string;
  post_count?: number;
  last_seen?: string;
  platforms?: string[];
}

const RISK_TONE: Record<string, string> = {
  high: 'bg-rose-500/15 text-rose-700 dark:text-rose-300',
  medium: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  low: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  none: 'bg-muted text-muted-foreground',
};

const RISK_LABEL: Record<string, string> = {
  high: '高危',
  medium: '中危',
  low: '低风险',
  none: '正常',
};

export function TopicListCard({ card }: CardProps) {
  const raw = (card.ui.data ?? card.data ?? {}) as { items?: TopicItem[] };
  const items = raw.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="my-2 p-4 text-center text-sm text-muted-foreground">
        暂无相关话题
      </Card>
    );
  }

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        话题 · {items.length} 条
      </div>
      <ul className="divide-y divide-border">
        {items.slice(0, 10).map((it, i) => {
          const risk = (it.risk_class ?? 'none').toLowerCase();
          return (
            <li key={it.topic_id ?? i} className="flex items-start gap-3 px-3 py-2.5">
              <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-muted">
                <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {it.topic_name ?? it.keyword ?? '(未命名)'}
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>{it.post_count ?? 0} 帖</span>
                  {it.platforms && it.platforms.length > 0 && (
                    <span>· {it.platforms.slice(0, 3).join(' / ')}</span>
                  )}
                  {it.last_seen && <span>· {it.last_seen.slice(0, 10)}</span>}
                </div>
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium',
                  RISK_TONE[risk] ?? RISK_TONE.none,
                )}
              >
                {RISK_LABEL[risk] ?? risk}
              </span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
