'use client';

/**
 * ScanProgressCard —— 扫描进度卡片（trigger_scan 流式结果）。
 *
 * 支持增量更新：每个 tool_progress 事件可更新 platforms / progress_pct。
 */
import { Card } from '@/components/ui/card';
import { Radio, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface ScanData {
  task_id?: string;
  started_at?: string;
  progress_pct?: number;
  status_text?: string;
  platforms?: Record<string, { scanned?: number; total?: number }>;
  done?: boolean;
}

export function ScanProgressCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as ScanData;
  const pct = d.progress_pct ?? 0;
  const done = d.done ?? pct >= 100;
  const platforms = d.platforms ?? {};

  return (
    <Card className="my-2 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
        <Radio className={cn('h-3 w-3', done ? 'text-emerald-500' : 'animate-pulse text-primary')} />
        <span className="text-xs font-medium text-muted-foreground">
          {done ? '扫描完成' : '正在扫描…'}
        </span>
        <span className="ml-auto text-[10px] tabular-nums text-muted-foreground">
          {Math.round(pct)}%
        </span>
      </div>
      <div className="p-3">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-all', done ? 'bg-emerald-500' : 'bg-primary')}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        {d.status_text && (
          <div className="mt-2 text-[11px] text-muted-foreground">{d.status_text}</div>
        )}
        {Object.keys(platforms).length > 0 && (
          <div className="mt-2 grid grid-cols-2 gap-1">
            {Object.entries(platforms).map(([key, val]) => {
              const s = val as { scanned?: number; total?: number };
              const done = s.total !== undefined && s.scanned !== undefined && s.scanned >= s.total;
              return (
                <div key={key} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  {done ? <Check className="h-2.5 w-2.5 text-emerald-500" /> : <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary/50" />}
                  <span className="capitalize">{key}</span>
                  <span className="tabular-nums">
                    {s.scanned ?? 0}/{s.total ?? '?'}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}
