'use client';

/** ScanStatusCard —— 扫描状态卡片（get_scan_status） */
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

export function ScanStatusCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    is_running?: boolean;
    status_text?: string;
    last_run_time?: string;
    progress_pct?: number;
  };
  const running = !!d.is_running;

  return (
    <Card className="my-2 overflow-hidden">
      <div className="flex items-center gap-2 p-3">
        <span
          className={cn(
            'h-2.5 w-2.5 shrink-0 rounded-full',
            running ? 'bg-emerald-500' : 'bg-muted-foreground/40',
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {running ? '扫描中' : '扫描待命'}
          </div>
          {d.status_text && (
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {d.status_text}
            </div>
          )}
        </div>
        {d.last_run_time && (
          <div className="shrink-0 text-[10px] text-muted-foreground">
            {d.last_run_time.slice(5, 16)}
          </div>
        )}
      </div>
      {running && d.progress_pct !== undefined && (
        <div className="h-1 w-full bg-muted">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${Math.min(100, d.progress_pct)}%` }}
          />
        </div>
      )}
    </Card>
  );
}
