'use client';

/**
 * RightDashboard —— Agent 页面右侧 4 模块看板。
 *
 * 模块：
 *   1. 今日概览（雷达状态 + 今日话题数）
 *   2. 订阅热度（暂时用 today_summary 占位）
 *   3. 平台分布（占位 placeholder）
 *   4. 快捷操作（点击塞入 Chat 框）
 *
 * 数据源走 TanStack Query，自带缓存。
 */
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Radio, TrendingUp, BarChart3, Zap, ChevronRight } from 'lucide-react';
import { radarApi } from '@/lib/api';

const QUICK_ACTIONS = [
  '展示我的订阅清单',
  '看看今天的高危话题',
  '触发一次全网扫描',
  '检查推送通道状态',
];

interface Props {
  onQuickAction?: (text: string) => void;
}

export function RightDashboard({ onQuickAction }: Props) {
  const statusQ = useQuery({
    queryKey: ['radar-status'],
    queryFn: () => radarApi.status(),
    refetchInterval: 10_000,
  });

  const todayQ = useQuery({
    queryKey: ['today-summary'],
    queryFn: () => radarApi.todaySummary(),
    refetchInterval: 60_000,
  });

  const scheduler = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => radarApi.schedulerStatus(),
    refetchInterval: 30_000,
  });

  return (
    <div className="flex flex-col gap-3 overflow-y-auto pb-2">
      {/* 1. 今日概览 */}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
          <Radio className="h-3 w-3 text-violet-500" />
          <span className="text-xs font-medium text-muted-foreground">
            今日概览
          </span>
        </div>
        <div className="space-y-2 p-3">
          {statusQ.isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  statusQ.data?.is_running ? 'animate-pulse bg-emerald-500' : 'bg-muted-foreground/40'
                }`}
              />
              <span className="text-sm font-medium">
                {statusQ.data?.is_running ? '雷达运行中' : '雷达待命'}
              </span>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
            <Stat
              label="新增"
              value={statusQ.data?.last_new_count ?? 0}
              hint="本次扫描"
            />
            <Stat
              label="高危"
              value={todayQ.data?.high_risk_count ?? 0}
              hint="今日累计"
            />
          </div>
          {scheduler.data?.next_run && (
            <div className="border-t border-border pt-2 text-[10px] text-muted-foreground">
              下次扫描 · {scheduler.data.next_run.slice(11, 16)}
            </div>
          )}
        </div>
      </Card>

      {/* 2. 订阅热度（v2 订阅未启用，用 today_summary 关键词占位） */}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
          <TrendingUp className="h-3 w-3 text-emerald-500" />
          <span className="text-xs font-medium text-muted-foreground">
            热门关注
          </span>
        </div>
        <div className="p-3">
          {todayQ.isLoading ? (
            <Skeleton className="h-12 w-full" />
          ) : todayQ.data?.keyword ? (
            <div>
              <div className="text-sm font-medium">{todayQ.data.keyword}</div>
              {todayQ.data.summary && (
                <p className="mt-1 line-clamp-3 text-[11px] text-muted-foreground">
                  {todayQ.data.summary}
                </p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">暂无热点</p>
          )}
        </div>
      </Card>

      {/* 3. 平台分布 */}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
          <BarChart3 className="h-3 w-3 text-blue-500" />
          <span className="text-xs font-medium text-muted-foreground">
            风险分布
          </span>
        </div>
        <div className="space-y-2 p-3">
          <DistBar
            label="高"
            value={todayQ.data?.risk_distribution?.high ?? 0}
            color="bg-rose-500"
          />
          <DistBar
            label="中"
            value={todayQ.data?.risk_distribution?.medium ?? 0}
            color="bg-amber-500"
          />
          <DistBar
            label="低"
            value={todayQ.data?.risk_distribution?.low ?? 0}
            color="bg-emerald-500"
          />
        </div>
      </Card>

      {/* 4. 快捷操作 */}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
          <Zap className="h-3 w-3 text-amber-500" />
          <span className="text-xs font-medium text-muted-foreground">
            快捷操作
          </span>
        </div>
        <div className="p-2">
          {QUICK_ACTIONS.map((q) => (
            <Button
              key={q}
              variant="ghost"
              size="sm"
              onClick={() => onQuickAction?.(q)}
              className="group h-auto w-full justify-between px-2 py-1.5 text-left text-xs font-normal"
            >
              <span className="truncate">{q}</span>
              <ChevronRight className="h-3 w-3 shrink-0 opacity-40 transition-transform group-hover:translate-x-0.5 group-hover:opacity-100" />
            </Button>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="rounded-md bg-muted/40 px-2 py-1.5">
      <div className="text-base font-semibold leading-none">{value}</div>
      <div className="mt-1 text-[10px] text-muted-foreground">{label}</div>
      {hint && <div className="text-[9px] text-muted-foreground/70">{hint}</div>}
    </div>
  );
}

function DistBar({ label, value, color }: { label: string; value: number; color: string }) {
  const max = 50; // 视觉归一
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-4 text-muted-foreground">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-6 text-right tabular-nums text-muted-foreground">{value}</span>
    </div>
  );
}
