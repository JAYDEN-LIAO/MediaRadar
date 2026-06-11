'use client';

/** TestResultCard —— 测试结果（test_channel / test_model） */
import { Card } from '@/components/ui/card';
import { Check, X, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

export function TestResultCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    success?: boolean;
    latency_ms?: number;
    error?: string;
    message?: string;
  };
  const ok = d.success === true;

  return (
    <Card className={cn('my-2 overflow-hidden', ok ? 'border-emerald-500/20' : 'border-rose-500/20')}>
      <div className="flex items-start gap-3 p-3">
        <div
          className={cn(
            'mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full',
            ok ? 'bg-emerald-500/15 text-emerald-600' : 'bg-rose-500/15 text-rose-600',
          )}
        >
          {ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className={cn('text-sm font-medium', ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300')}>
            {ok ? '测试通过' : '测试失败'}
          </div>
          {d.latency_ms !== undefined && (
            <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>{d.latency_ms}ms</span>
            </div>
          )}
          {d.error && <div className="mt-1 text-[11px] text-rose-600 dark:text-rose-400">{d.error}</div>}
          {d.message && <div className="mt-1 text-[11px] text-muted-foreground">{d.message}</div>}
        </div>
      </div>
    </Card>
  );
}
