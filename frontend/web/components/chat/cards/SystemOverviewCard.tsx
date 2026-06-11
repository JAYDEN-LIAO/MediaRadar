'use client';

/**
 * SystemOverviewCard —— 系统概览
 *
 * data: {
 *   subscriptions: { active, paused, total },
 *   topics: { today, week, total },
 *   crawl: { last_run, next_run, status },
 *   alerts: { high, medium },
 * }
 */
import { Card } from '@/components/ui/card';
import { Activity, Bell, Radio, AlertTriangle } from 'lucide-react';
import type { CardProps } from './registry';

interface Overview {
  subscriptions?: { active?: number; total?: number };
  topics?: { today?: number; total?: number };
  crawl?: { last_run?: string; next_run?: string; status?: string };
  alerts?: { high?: number; medium?: number };
}

export function SystemOverviewCard({ card }: CardProps) {
  const data = (card.ui.data ?? card.data ?? {}) as Overview;
  const tiles = [
    {
      label: '生效订阅',
      value: data.subscriptions?.active ?? 0,
      sub: `总 ${data.subscriptions?.total ?? 0}`,
      Icon: Bell,
      tone: 'text-blue-500',
    },
    {
      label: '今日话题',
      value: data.topics?.today ?? 0,
      sub: `总 ${data.topics?.total ?? 0}`,
      Icon: Activity,
      tone: 'text-emerald-500',
    },
    {
      label: '高危预警',
      value: data.alerts?.high ?? 0,
      sub: `中危 ${data.alerts?.medium ?? 0}`,
      Icon: AlertTriangle,
      tone: 'text-rose-500',
    },
    {
      label: '雷达状态',
      value: data.crawl?.status ?? '—',
      sub: data.crawl?.next_run?.slice(11, 16) ?? '',
      Icon: Radio,
      tone: 'text-violet-500',
    },
  ];

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        系统概览
      </div>
      <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
        {tiles.map(({ label, value, sub, Icon, tone }) => (
          <div
            key={label}
            className="rounded-lg border border-border bg-card/40 p-3"
          >
            <Icon className={`h-4 w-4 ${tone}`} />
            <div className="mt-2 text-lg font-semibold leading-none">
              {value}
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground">{label}</div>
            {sub && (
              <div className="mt-0.5 text-[10px] text-muted-foreground/70">
                {sub}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
