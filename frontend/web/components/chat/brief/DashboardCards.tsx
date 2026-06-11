'use client';

/** DashboardCards —— 登录简报中的今日总览卡片组 */
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { radarApi } from '@/lib/api';

export function DashboardCards() {
  const status = useQuery({
    queryKey: ['radar-status'],
    queryFn: () => radarApi.status(),
    refetchInterval: 30_000,
  });
  const today = useQuery({
    queryKey: ['today-summary'],
    queryFn: () => radarApi.todaySummary(),
    refetchInterval: 60_000,
  });

  if (status.isLoading && today.isLoading) {
    return (
      <Card className="overflow-hidden p-3">
        <Skeleton className="h-20 w-full" />
      </Card>
    );
  }

  const scanCount = status.data?.last_new_count ?? 0;
  const highRisk = today.data?.high_risk_count ?? 0;
  const riskDist = today.data?.risk_distribution;
  const suppressed = today.data?.suppressed_count ?? 0;

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        今日总览
      </div>
      <div className="grid grid-cols-2 gap-3 p-3 sm:grid-cols-4">
        <Tile label="扫描" value={`${scanCount}`} hint="次话题" />
        <Tile label="高危" value={`${highRisk}`} hint={`中危 ${riskDist?.medium ?? 0}`} tone={highRisk > 0 ? 'text-rose-600' : ''} />
        <Tile label="已推送" value="-" hint="Agent 决策" />
        <Tile label="状态" value={status.data?.is_running ? '运行中' : '待命'} hint="雷达" />
      </div>
      {suppressed > 0 && (
        <div className="border-t border-border bg-amber-500/5 px-3 py-1.5 text-[10px] text-amber-600 dark:text-amber-400">
          Agent 压住了 {suppressed} 条推送
        </div>
      )}
    </Card>
  );
}

function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: string }) {
  return (
    <div className="rounded-md bg-muted/40 p-2">
      <div className={`text-base font-semibold leading-none ${tone ?? ''}`}>{value}</div>
      <div className="mt-1 text-[10px] text-muted-foreground">{label}</div>
      {hint && <div className="text-[9px] text-muted-foreground/70">{hint}</div>}
    </div>
  );
}
