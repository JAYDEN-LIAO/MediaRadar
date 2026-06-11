'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Gauge, Activity, AlertCircle, Loader2 } from 'lucide-react';

interface AdminStats {
  total_users: number;
  total_subscriptions: number;
  active_subscriptions: number;
  today_topics: number;
  scheduler_active: boolean;
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('mediaradar_token');
}

export default function AdminHomePage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
    const token = getToken();
    fetch(`${apiBase}/api/admin/stats`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(j => { if (j?.data) setStats(j.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">管理总览</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          MediaRadar v2.2 · 多用户 SaaS · 订阅平台
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">注册用户</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats?.total_users ?? '—'}</div>
            <p className="mt-1 text-xs text-muted-foreground/60">
              <a href="/admin/users" className="text-primary hover:underline">查看用户管理</a>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">活跃订阅</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats?.active_subscriptions ?? '—'}</div>
            <p className="mt-1 text-xs text-muted-foreground/60">
              总共 {stats?.total_subscriptions ?? 0} 条 · 跨用户汇总
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">今日话题</CardTitle>
            <Gauge className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{stats?.today_topics ?? '—'}</div>
            <p className="mt-1 text-xs text-muted-foreground/60">过去 24 小时活跃话题</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">调度器</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-semibold ${stats?.scheduler_active ? 'text-emerald-600' : 'text-muted-foreground'}`}>
              {stats?.scheduler_active ? '运行中' : '已停止'}
            </div>
            <p className="mt-1 text-xs text-muted-foreground/60">
              {stats?.scheduler_active ? '定时扫描已启用' : '需手动启动调度器'}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>快捷入口</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>· <a href="/admin/users" className="text-primary hover:underline">用户管理</a> — 搜索、禁用用户</p>
          <p>· <a href="/admin/quota" className="text-primary hover:underline">配额调整</a> — 查看和修改用户配额</p>
          <p>· <a href="/dashboard" className="text-primary hover:underline">全局仪表盘</a> — 系统级数据视图</p>
          <p>· <a href="/settings/system" className="text-primary hover:underline">系统设置</a> — 关键词 / 平台 / 推送配置</p>
        </CardContent>
      </Card>
    </div>
  );
}
