'use client';

/** SchedulerInfoCard —— 调度器信息（set_scan_interval / pause / resume / get_next_run_time） */
import { Card } from '@/components/ui/card';
import { Clock, Play, Pause } from 'lucide-react';
import type { CardProps } from './registry';

export function SchedulerInfoCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    next_run_at?: string;
    interval_min?: number;
    active?: boolean;
  };
  const active = d.active !== false;

  return (
    <Card className="my-2 p-3">
      <div className="flex items-center gap-2">
        <Clock className="h-4 w-4 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {active ? '定时扫描已启用' : '定时扫描已暂停'}
          </div>
          {d.interval_min && (
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              每 {d.interval_min} 分钟
            </div>
          )}
          {d.next_run_at && (
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              下次：{d.next_run_at.slice(5, 16)}
            </div>
          )}
        </div>
        <div className={`shrink-0 rounded-full p-1.5 ${active ? 'bg-emerald-500/15 text-emerald-600' : 'bg-muted text-muted-foreground'}`}>
          {active ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
        </div>
      </div>
    </Card>
  );
}
