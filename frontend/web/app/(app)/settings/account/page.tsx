'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Shield, Bell } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { authApi } from '@/lib/api';

export default function AccountSettingsPage() {
  const { data: user, isLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: () => authApi.me(),
  });

  const [notifications, setNotifications] = useState({
    '高风险舆情告警': true,
    '每日简报': true,
    '系统更新': false,
  });

  const toggle = (label: string) =>
    setNotifications((prev) => ({ ...prev, [label]: !prev[label as keyof typeof prev] }));

  return (
    <div className="space-y-6">
      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">个人资料</CardTitle>
          <CardDescription>头像与基本信息</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16">
              <AvatarFallback className="bg-primary/20 text-lg text-primary">
                {user?.nickname?.[0]?.toUpperCase() || 'U'}
              </AvatarFallback>
            </Avatar>
            <div>
              {isLoading ? (
                <Skeleton className="h-5 w-32" />
              ) : (
                <>
                  <div className="text-lg font-semibold">{user?.nickname || '用户'}</div>
                  <div className="text-sm text-muted-foreground">
                    {user?.email || ''}
                    {user?.role === 'admin' ? ' · 管理员' : ''}
                    {user?.oauth_provider ? ` · ${user.oauth_provider} 登录` : ' · 邮箱登录'}
                  </div>
                </>
              )}
            </div>
          </div>
          <Separator />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>昵称</Label>
              <Input defaultValue={user?.nickname || ''} />
            </div>
            <div className="space-y-1.5">
              <Label>邮箱</Label>
              <Input defaultValue={user?.email || ''} disabled />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bell className="h-4 w-4" /> 通知偏好
          </CardTitle>
          <CardDescription>控制哪些事件需要提醒</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { label: '高风险舆情告警', desc: '风险等级 ≥ 4 的事件实时通知' },
            { label: '每日简报', desc: '每天 20:00 推送当日舆情汇总' },
            { label: '系统更新', desc: '新功能与版本更新提醒' },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <div className="text-sm font-medium">{item.label}</div>
                <div className="text-xs text-muted-foreground">{item.desc}</div>
              </div>
              <Switch
                checked={notifications[item.label as keyof typeof notifications]}
                onCheckedChange={() => toggle(item.label)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="h-4 w-4" /> 安全
          </CardTitle>
          <CardDescription>登录方式与会话管理</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div className="flex items-center gap-3">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <div>
                <div className="text-sm font-medium">双因素认证</div>
                <div className="text-xs text-muted-foreground">即将上线</div>
              </div>
            </div>
            <Switch disabled />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
