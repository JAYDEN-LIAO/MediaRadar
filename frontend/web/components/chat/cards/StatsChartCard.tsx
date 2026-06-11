'use client';

/**
 * StatsChartCard —— 统计图表卡片（get_subscription_stats）。
 *
 * 使用 recharts 渲染折线图 + 饼图。
 *
 * data: {
 *   topic_count, trend_data: [{ date, count }],
 *   platform_dist: [{ platform, count }],
 *   push_stats: { pushed, suppressed, total }
 * }
 */
import {
  LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { Card } from '@/components/ui/card';
import { TrendingUp, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

const COLORS = ['#6366f1', '#f59e0b', '#22c55e', '#ef4444', '#8b5cf6', '#06b6d4'];

interface TrendPoint { date?: string; count?: number; }
interface PlatformDist { platform?: string; count?: number; }
interface PushStats { pushed?: number; suppressed?: number; total?: number; }

export function StatsChartCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    topic_count?: number;
    trend_data?: TrendPoint[];
    platform_dist?: PlatformDist[];
    push_stats?: PushStats;
  };

  return (
    <Card className="my-2 overflow-hidden p-3">
      {/* 折线图 */}
      {d.trend_data && d.trend_data.length > 0 && (
        <div className="mb-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <TrendingUp className="h-3.5 w-3.5" />
            趋势
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={d.trend_data}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} width={30} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 饼图 */}
      {d.platform_dist && d.platform_dist.length > 0 && (
        <div className="mb-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <BarChart3 className="h-3.5 w-3.5" />
            平台分布
          </div>
          <div className="flex items-center gap-4">
            <div className="h-32 w-32 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={d.platform_dist.map((p) => ({ name: p.platform, value: p.count }))}
                    cx="50%"
                    cy="50%"
                    outerRadius={45}
                    dataKey="value"
                  >
                    {d.platform_dist.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-1">
              {d.platform_dist.map((p, i) => (
                <div key={i} className="flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span>{p.platform}</span>
                  <span className="tabular-nums">{p.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 推送统计 */}
      {d.push_stats && (
        <div className="grid grid-cols-3 gap-2 rounded-lg bg-muted/40 p-2">
          <div className="text-center">
            <div className="text-sm font-semibold">{d.push_stats.pushed ?? 0}</div>
            <div className="text-[10px] text-muted-foreground">已推送</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold text-amber-600">{d.push_stats.suppressed ?? 0}</div>
            <div className="text-[10px] text-muted-foreground">已压住</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-semibold">{d.push_stats.total ?? 0}</div>
            <div className="text-[10px] text-muted-foreground">总计</div>
          </div>
        </div>
      )}
    </Card>
  );
}
