'use client';

/** ActivityTimelineCard —— 最近活动时间线（get_recent_activity） */
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Radio, Bell, Search, Settings, Activity } from 'lucide-react';
import type { CardProps } from './registry';

interface ActivityEvent {
  type?: string;
  summary?: string;
  timestamp?: string;
  details?: string;
}

const ICON_MAP: Record<string, typeof Radio> = {
  scan: Radio,
  push: Bell,
  search: Search,
  config: Settings,
  alert: Bell,
};
const DEFAULT_ICON = Activity;

export function ActivityTimelineCard({ card }: CardProps) {
  const raw = (card.ui?.data ?? card.data ?? {}) as { items?: ActivityEvent[] };
  const items = raw.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="my-2 p-4 text-center text-xs text-muted-foreground">
        暂无活动记录
      </Card>
    );
  }

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        最近活动
      </div>
      <div className="p-3">
        <div className="relative space-y-0">
          {items.slice(0, 15).map((it, i) => {
            const Icon = ICON_MAP[it.type ?? ''] ?? DEFAULT_ICON;
            const isLast = i === Math.min(items.length - 1, 14);
            return (
              <div key={i} className="relative flex gap-3 pb-4">
                {/* 连线 */}
                {!isLast && (
                  <div className="absolute left-[11px] top-5 bottom-0 w-px bg-border" />
                )}
                {/* 图标 */}
                <div className="z-10 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-muted">
                  <Icon className="h-3 w-3 text-muted-foreground" />
                </div>
                {/* 内容 */}
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium">{it.summary ?? it.type ?? '事件'}</div>
                  {it.details && (
                    <div className="mt-0.5 text-[10px] text-muted-foreground/70 line-clamp-2">
                      {it.details}
                    </div>
                  )}
                  {it.timestamp && (
                    <div className="mt-0.5 text-[9px] text-muted-foreground/50">
                      {it.timestamp.slice(0, 16)}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
