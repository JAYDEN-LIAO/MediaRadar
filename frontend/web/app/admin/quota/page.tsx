'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Save } from 'lucide-react';

export default function AdminQuotaPage() {
  const [defaults, setDefaults] = useState({
    max_subscriptions: 20,
    history_retention_days: 30,
    max_chat_per_month: 200,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // 显示系统默认（不可改，仅展示）
    // P1+ 可以加 admin 改全局默认的功能
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      // 实际功能：可以选一个用户 ID 调整其配额
      // 这里简化为显示默认 + 占位说明
      toast.info('P0 阶段：调整全局默认请编辑 .env 或改 quota_db.py 常量');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">配额调整</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          系统默认配额（v2.2）：每个新用户自动应用以下限制
        </p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>默认配额</CardTitle>
          <CardDescription>
            这些值定义在 <code className="rounded bg-muted px-1.5 py-0.5 text-xs">backend/core/quota_db.py</code>，修改后需重启服务。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="max_subs">最大订阅数</Label>
            <Input
              id="max_subs"
              type="number"
              value={defaults.max_subscriptions}
              onChange={e => setDefaults(d => ({ ...d, max_subscriptions: +e.target.value }))}
              min={1}
              max={1000}
            />
            <p className="text-xs text-muted-foreground/60">每用户可添加的订阅上限</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="retention">历史保留天数</Label>
            <Input
              id="retention"
              type="number"
              value={defaults.history_retention_days}
              onChange={e => setDefaults(d => ({ ...d, history_retention_days: +e.target.value }))}
              min={1}
              max={365}
            />
            <p className="text-xs text-muted-foreground/60">原始帖子保留 N 天后清理，话题永久</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="max_chat">每月 Chat 消息上限</Label>
            <Input
              id="max_chat"
              type="number"
              value={defaults.max_chat_per_month}
              onChange={e => setDefaults(d => ({ ...d, max_chat_per_month: +e.target.value }))}
              min={1}
              max={10000}
            />
            <p className="text-xs text-muted-foreground/60">每月 1 日自动重置（30 天滚动）</p>
          </div>

          <Button onClick={handleSave} disabled className="opacity-60">
            <Save className="mr-1.5 h-4 w-4" />
            保存（v1+ 实现）
          </Button>
        </CardContent>
      </Card>

      <Card className="max-w-xl border-dashed">
        <CardHeader>
          <CardTitle className="text-base">按用户调整</CardTitle>
          <CardDescription>
            v1+ 实现：列出所有用户 → 点进用户 → 编辑其配额。当前请用 API：
            <code className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">PUT /api/admin/users/{'{id}'}/quota</code>
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
