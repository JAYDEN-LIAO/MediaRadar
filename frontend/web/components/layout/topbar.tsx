'use client';

import Link from 'next/link';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { radarApi, authApi } from '@/lib/api';

export function Topbar() {
  const { theme, setTheme } = useTheme();

  const scheduler = useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => radarApi.schedulerStatus(),
    refetchInterval: 10_000,
  });

  const { data: user } = useQuery({
    queryKey: ['current-user'],
    queryFn: () => authApi.me(),
  });

  const nextRun = scheduler.data?.next_run;
  const active = scheduler.data?.active ?? false;

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-border/50 bg-background px-6">
      {/* ① 左侧：调度信息 */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground/60">
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${active ? 'bg-emerald-500' : 'bg-muted-foreground/30'}`} />
        {active ? (
          nextRun
            ? <span>下次扫描 {new Date(nextRun).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>
            : <span>调度器运行中</span>
        ) : (
          <span>调度器未启动</span>
        )}
      </div>

      {/* ② 中间弹性空白 */}
      <div className="flex-1" />

      {/* ③ 右侧：主题切换 + 用户头像 */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        className="h-7 w-7 text-muted-foreground/50 hover:text-[oklch(0.6_0.18_285)]"
      >
        <Sun className="h-3.5 w-3.5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-3.5 w-3.5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </Button>

      {user && (
        <Link href="/settings/account" className="flex items-center gap-2 text-xs text-muted-foreground/60 hover:text-foreground transition-colors">
          <Avatar className="h-6 w-6">
            <AvatarFallback className="text-[10px] bg-muted text-foreground/70">
              {user.nickname?.[0]?.toUpperCase() || 'U'}
            </AvatarFallback>
          </Avatar>
          <span className="hidden sm:inline">{user.nickname}</span>
        </Link>
      )}
    </header>
  );
}
