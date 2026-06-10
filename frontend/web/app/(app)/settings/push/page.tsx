'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, MessageSquare, Send, Loader2, Check, Plus, X, TestTube } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { pushApi, type PushConfig } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const emailSchema = z.object({
  enabled: z.boolean(),
  risk_min_level: z.number().min(1).max(5),
  smtp_host: z.string().min(1, 'SMTP 主机必填'),
  smtp_port: z.number().min(1).max(65535),
  smtp_user: z.string().min(1, '用户名必填'),
  smtp_password: z.string().optional(),
  smtp_use_tls: z.boolean(),
  from_addr: z.string().email('发件人邮箱格式错误'),
  to_addrs: z.array(z.string().email('收件人邮箱格式错误')).min(1, '至少 1 个收件人'),
});

const webhookSchema = z.object({
  enabled: z.boolean(),
  risk_min_level: z.number().min(1).max(5),
  webhook_url: z.string().url('Webhook URL 格式错误'),
});

type EmailValues = z.infer<typeof emailSchema>;
type WebhookValues = z.infer<typeof webhookSchema>;

const channels = [
  { id: 'email', name: '邮件', icon: Mail, desc: 'SMTP 邮件告警' },
  { id: 'wecom', name: '企业微信', icon: MessageSquare, desc: '群机器人 Webhook' },
  { id: 'feishu', name: '飞书', icon: Send, desc: '群机器人 Webhook' },
] as const;

export default function PushSettingsPage() {
  const [activeTab, setActiveTab] = useState<string>('email');

  const { data: configs, isLoading } = useQuery({
    queryKey: ['push-configs'],
    queryFn: () => pushApi.configs(),
  });

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {channels.map((c) => (
            <TabsTrigger key={c.id} value={c.id} className="gap-2">
              <c.icon className="h-4 w-4" />
              {c.name}
            </TabsTrigger>
          ))}
        </TabsList>

        {isLoading ? (
          <Card className="mt-4">
            <CardContent className="py-8">
              <Skeleton className="h-40 w-full" />
            </CardContent>
          </Card>
        ) : (
          <>
            <TabsContent value="email" forceMount className={cn('space-y-4', activeTab !== 'email' && 'hidden')}>
              <EmailForm config={configs?.email} />
            </TabsContent>
            <TabsContent value="wecom" forceMount className={cn('space-y-4', activeTab !== 'wecom' && 'hidden')}>
              <WebhookForm channel="wecom" name="企业微信" config={configs?.wecom} />
            </TabsContent>
            <TabsContent value="feishu" forceMount className={cn('space-y-4', activeTab !== 'feishu' && 'hidden')}>
              <WebhookForm channel="feishu" name="飞书" config={configs?.feishu} />
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}

function EmailForm({ config }: { config?: PushConfig }) {
  const qc = useQueryClient();
  const [emailDraft, setEmailDraft] = useState('');
  const form = useForm<EmailValues>({
    resolver: zodResolver(emailSchema),
    values: config as EmailValues | undefined,
    defaultValues: config as EmailValues | undefined,
  });
  const watched = form.watch();
  const toAddrs = watched.to_addrs ?? [];

  const save = useMutation({
    mutationFn: (v: EmailValues) => pushApi.save('email', v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['push-configs'] });
      toast.success('邮件配置已保存');
    },
  });

  const test = useMutation({
    mutationFn: () => pushApi.test('email'),
    onSuccess: (r) => toast.success(r.msg || '测试成功'),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mail className="h-4 w-4" /> 邮件推送配置
            </CardTitle>
            <CardDescription>通过 SMTP 发送预警邮件，支持 TLS</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs">启用</Label>
            <Switch
              checked={watched.enabled}
              onCheckedChange={(v) => form.setValue('enabled', v)}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>SMTP 主机</Label>
              <Input {...form.register('smtp_host')} placeholder="smtp.example.com" />
            </div>
            <div className="space-y-2">
              <Label>SMTP 端口</Label>
              <Input type="number" {...form.register('smtp_port', { valueAsNumber: true })} />
            </div>
            <div className="space-y-2">
              <Label>用户名</Label>
              <Input {...form.register('smtp_user')} />
            </div>
            <div className="space-y-2">
              <Label>密码</Label>
              <Input type="password" {...form.register('smtp_password')} placeholder="留空保留原密码" />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>发件人邮箱</Label>
              <Input type="email" {...form.register('from_addr')} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>收件人邮箱</Label>
              <div className="flex gap-2">
                <Input
                  type="email"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (emailDraft) {
                        form.setValue('to_addrs', [...toAddrs, emailDraft], { shouldValidate: true });
                        setEmailDraft('');
                      }
                    }
                  }}
                  placeholder="回车添加"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    if (emailDraft) {
                      form.setValue('to_addrs', [...toAddrs, emailDraft], { shouldValidate: true });
                      setEmailDraft('');
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {toAddrs.map((a) => (
                  <Badge key={a} variant="secondary" className="gap-1 pl-3 pr-1.5">
                    {a}
                    <button
                      type="button"
                      onClick={() => form.setValue('to_addrs', toAddrs.filter((x) => x !== a), { shouldValidate: true })}
                      className="rounded p-0.5 hover:bg-destructive/20"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label className="text-sm">启用 TLS</Label>
            <Switch
              checked={watched.smtp_use_tls}
              onCheckedChange={(v) => form.setValue('smtp_use_tls', v)}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label className="text-sm">最低告警风险等级（1-5）</Label>
            <Input
              type="number"
              min={1}
              max={5}
              className="w-20"
              {...form.register('risk_min_level', { valueAsNumber: true })}
            />
          </div>

          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={() => test.mutate()} disabled={test.isPending || !watched.enabled}>
              <TestTube className="mr-2 h-4 w-4" /> 发送测试
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              保存配置
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function WebhookForm({ channel, name, config }: { channel: string; name: string; config?: PushConfig }) {
  const qc = useQueryClient();
  const form = useForm<WebhookValues>({
    resolver: zodResolver(webhookSchema),
    values: config as WebhookValues | undefined,
    defaultValues: config as WebhookValues | undefined,
  });
  const watched = form.watch();

  const save = useMutation({
    mutationFn: (v: WebhookValues) => pushApi.save(channel, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['push-configs'] });
      toast.success(`${name} 配置已保存`);
    },
  });
  const test = useMutation({
    mutationFn: () => pushApi.test(channel),
    onSuccess: (r) => toast.success(r.msg || '测试成功'),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="h-4 w-4" /> {name} Webhook 配置
            </CardTitle>
            <CardDescription>填写 {name} 群机器人 Webhook URL</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs">启用</Label>
            <Switch
              checked={watched.enabled}
              onCheckedChange={(v) => form.setValue('enabled', v)}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="space-y-4">
          <div className="space-y-2">
            <Label>Webhook URL</Label>
            <Input {...form.register('webhook_url')} placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label className="text-sm">最低告警风险等级（1-5）</Label>
            <Input
              type="number"
              min={1}
              max={5}
              className="w-20"
              {...form.register('risk_min_level', { valueAsNumber: true })}
            />
          </div>
          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={() => test.mutate()} disabled={test.isPending || !watched.enabled}>
              <TestTube className="mr-2 h-4 w-4" /> 发送测试
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              保存配置
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
