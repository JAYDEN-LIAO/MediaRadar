'use client';

import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, Eye, TrendingUp, Clock, Globe } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AnimatedNumber } from '@/components/animated-number';
import { radarApi } from '@/lib/api';
import { VolumeChart, RiskPieChart } from '@/components/charts';

export default function DashboardPage() {
  const status = useQuery({
    queryKey: ['radar-status'],
    queryFn: () => radarApi.status(),
    refetchInterval: 3000,
  });
  const summary = useQuery({
    queryKey: ['today-summary'],
    queryFn: () => radarApi.todaySummary(),
    refetchInterval: 10_000,
  });
  const volume = useQuery({
    queryKey: ['volume-stats'],
    queryFn: () => radarApi.volumeStats(),
    refetchInterval: 30_000,
  });
  const scheduler = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => radarApi.schedulerStatus(),
    refetchInterval: 10_000,
  });
  const topics = useQuery({
    queryKey: ['topic-list-dash'],
    queryFn: () => radarApi.topicList({ limit: 200 }),
    refetchInterval: 30_000,
  });

  if (status.error && summary.error && volume.error) {
    return (
      <div className="flex flex-col items-center gap-3 pt-20 text-sm text-muted-foreground/60">
        <p>无法连接后端服务</p>
        <button onClick={() => { status.refetch(); summary.refetch(); volume.refetch(); }} className="text-primary underline">重试</button>
      </div>
    );
  }

  const isRunning = status.data?.is_running ?? false;
  const lastRun = status.data?.last_run_time ?? '';
  const lastCount = status.data?.last_new_count ?? 0;
  const total = volume.data?.total ?? 0;
  const negTotal = volume.data?.negative_total ?? 0;
  const highRisk = summary.data?.high_risk_count ?? 0;
  const riskDist = summary.data?.risk_distribution ?? { high: 0, medium: 0, low: 0 };
  const nextRun = scheduler.data?.next_run ?? '';

  // 平台分布（从话题列表统计）
  const topicItems: Array<Record<string, unknown>> = (topics.data ?? []) as unknown as Array<Record<string, unknown>>;
  const platformMap: Record<string, number> = {};
  topicItems.forEach((t: Record<string, unknown>) => {
    const plats = (t.platforms as unknown as string[]) ?? [];
    plats.forEach((p: string) => { platformMap[p] = (platformMap[p] || 0) + 1; });
  });
  const platNames: Record<string, string> = { wb: '微博', xhs: '小红书', bili: 'B站', zhihu: '知乎', dy: '抖音', ks: '快手', tieba: '贴吧' };
  const platformEntries = Object.entries(platformMap).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-5 pt-2">
      {/* 统计栏 */}
      <div className="flex flex-wrap items-center gap-x-10 gap-y-3">
        <StatItem icon={Activity} label="雷达" value={isRunning ? '运行中' : '待命中'} />
        <div className="h-6 w-px bg-border/50" />
        <StatItem icon={TrendingUp} label="今日声量" value={volume.isLoading ? '…' : <AnimatedNumber value={total} />} />
        <div className="h-6 w-px bg-border/50" />
        <StatItem icon={AlertTriangle} label="高风险" value={summary.isLoading ? '…' : <AnimatedNumber value={highRisk} />} />
        <div className="h-6 w-px bg-border/50" />
        <StatItem icon={Eye} label="负面占比" value={total > 0 ? `${((negTotal / total) * 100).toFixed(0)}%` : '0%'} />
      </div>

      {/* 信息卡组：扫描+调度器 / 平台分布 / 最近入库 */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* ① 扫描 + 调度器（合并） */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground/60 uppercase tracking-wider">
              <Activity className="h-3 w-3" /> 扫描
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {status.isLoading && scheduler.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm">
                    <span className={`inline-block h-2 w-2 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-muted-foreground/30'}`} />
                    <span className="text-muted-foreground/70">{isRunning ? '扫描中' : '待命中'}</span>
                  </div>
                  <span className={`inline-block h-2 w-2 rounded-full ${scheduler.data?.active ? 'bg-emerald-500' : 'bg-muted-foreground/30'}`} title={scheduler.data?.active ? '调度器运行中' : '调度器已停止'} />
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                  <div>
                    <div className="text-muted-foreground/40">上次</div>
                    <div className="text-muted-foreground/70 truncate">{lastRun && lastRun !== '暂无' ? lastRun : '—'}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground/40">下次</div>
                    <div className="text-muted-foreground/70">{nextRun ? new Date(nextRun).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '—'}</div>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* ② 平台分布 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground/60 uppercase tracking-wider">
              <Globe className="h-3 w-3" /> 平台分布
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topics.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : platformEntries.length === 0 ? (
              <div className="text-xs text-muted-foreground/60">暂无数据</div>
            ) : (
              <div className="space-y-1">
                {platformEntries.slice(0, 5).map(([key, count]) => (
                  <div key={key} className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground/70">{platNames[key] || key}</span>
                    <span className="tabular-nums text-foreground/80">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ③ 最近入库 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground/60 uppercase tracking-wider">
              <Clock className="h-3 w-3" /> 最近入库
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topics.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : !topicItems.length ? (
              <div className="text-xs text-muted-foreground/60">暂无数据</div>
            ) : (
              <div className="space-y-1.5">
                {topicItems.slice(0, 5).map((t: Record<string, unknown>) => (
                  <div key={t.topic_id as string} className="truncate text-xs">
                    <span className="text-foreground/80">{String(t.topic_name || t.core_issue || '无标题')}</span>
                    <span className="ml-2 text-muted-foreground/40">{platNames[((t.platforms as unknown as string[])?.[0]) || ''] || ''}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* AI 摘要 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <p className="text-xs font-medium text-muted-foreground/60 uppercase tracking-wider">
              AI 舆情摘要
              {summary.data?.sentiment ? ` · ${summary.data.sentiment}` : ''}
            </p>
          </div>
        </CardHeader>
        <CardContent>
          {summary.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" /> <Skeleton className="h-4 w-4/5" /> <Skeleton className="h-4 w-2/3" />
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-foreground/80">{summary.data?.summary ?? '暂无数据'}</p>
          )}
        </CardContent>
      </Card>

      {/* 图表 */}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">近 7 日声量趋势</CardTitle>
          </CardHeader>
          <CardContent>
            {volume.data ? <VolumeChart data={volume.data} /> : <Skeleton className="h-[240px] w-full" />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">风险分布</CardTitle>
          </CardHeader>
          <CardContent>
            <RiskPieChart data={[
              { name: '高风险', value: riskDist.high || 0, color: '#f43f5e' },
              { name: '中风险', value: riskDist.medium || 0, color: '#f59e0b' },
              { name: '低风险', value: riskDist.low || 0, color: '#22c55e' },
            ]} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatItem({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="h-4 w-4 text-muted-foreground/40" />
      <div className="flex items-baseline gap-2">
        <span className="text-sm text-muted-foreground/60">{label}</span>
        <span className="text-lg font-semibold tabular-nums text-foreground">{value}</span>
      </div>
    </div>
  );
}
