'use client';

/** AlertListCard —— 预警/动态列表（search_alerts） */
import { Card } from '@/components/ui/card';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface AlertItem {
  id?: string;
  title?: string;
  content?: string;
  type?: 'alert' | 'dynamic';
  risk_level?: number;
  platform?: string;
  published_at?: string;
  summary?: string;
}

export function AlertListCard({ card }: CardProps) {
  const raw = (card.ui?.data ?? card.data ?? {}) as { items?: AlertItem[] };
  const items = raw.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="my-2 p-4 text-center text-xs text-muted-foreground">
        无结果
      </Card>
    );
  }

  return (
    <Card className="my-2 overflow-hidden">
      <ul className="divide-y divide-border">
        {items.slice(0, 10).map((it, i) => {
          const isAlert = it.type === 'alert' || (it.risk_level ?? 0) >= 3;
          return (
            <li key={it.id ?? i} className="flex items-start gap-3 px-3 py-2.5">
              <div
                className={cn(
                  'mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full',
                  isAlert
                    ? 'bg-rose-500/15 text-rose-600'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {isAlert
                  ? <AlertTriangle className="h-3 w-3" />
                  : <TrendingUp className="h-3 w-3" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium leading-snug">
                  {it.title ?? it.summary ?? '(无标题)'}
                </div>
                {it.content && (
                  <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">
                    {it.content}
                  </p>
                )}
                <div className="mt-1 flex gap-3 text-[10px] text-muted-foreground/70">
                  {it.platform && <span>{it.platform}</span>}
                  {it.published_at && <span>{it.published_at.slice(0, 10)}</span>}
                  {it.risk_level !== undefined && (
                    <span className={cn(
                      'font-medium',
                      it.risk_level >= 4 ? 'text-rose-500' : it.risk_level >= 3 ? 'text-amber-500' : '',
                    )}>
                      风险 Lv.{it.risk_level}
                    </span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
