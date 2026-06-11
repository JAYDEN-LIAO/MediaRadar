'use client';

/** HealthGridCard —— 组件健康检查网格（health_check） */
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface ComponentHealth {
  component?: string;
  status?: 'ok' | 'degraded' | 'down';
  latency_ms?: number;
  message?: string;
}

const STATUS_ICON: Record<string, string> = {
  ok: '●',
  degraded: '◐',
  down: '○',
};

const STATUS_TONE: Record<string, string> = {
  ok: 'text-emerald-500',
  degraded: 'text-amber-500',
  down: 'text-rose-500',
};

export function HealthGridCard({ card }: CardProps) {
  const raw = (card.ui?.data ?? card.data ?? {}) as { items?: ComponentHealth[] };
  const items = raw.items ?? [];

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        组件健康
      </div>
      <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-3">
        {items.map((it, i) => {
          const status = it.status ?? 'down';
          return (
            <div
              key={i}
              className={cn(
                'rounded-lg border border-border bg-card/40 p-2.5',
                status === 'down' && 'border-rose-500/20 bg-rose-500/5',
              )}
            >
              <div className="flex items-center gap-1.5">
                <span className={cn('text-xs', STATUS_TONE[status])}>
                  {STATUS_ICON[status]}
                </span>
                <span className="text-xs font-medium">
                  {it.component ?? 'unk'}
                </span>
              </div>
              {it.latency_ms !== undefined && (
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {it.latency_ms}ms
                </div>
              )}
              {it.message && (
                <div className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground/70">
                  {it.message}
                </div>
              )}
            </div>
          );
        })}
        {items.length === 0 && (
          <div className="col-span-full py-4 text-center text-xs text-muted-foreground">
            暂无健康数据
          </div>
        )}
      </div>
    </Card>
  );
}
