'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Plus, X, Save, Loader2, Power, PowerOff } from 'lucide-react';
import { useState } from 'react';
import { radarApi, type SystemSettings } from '@/lib/api';
import { toast } from 'sonner';

const schema = z.object({
  keywords: z.array(z.string().min(1)).min(1, '至少 1 个关键词'),
  inactive_keywords: z.array(z.string()),
  platforms: z.array(z.string()).min(1, '至少 1 个平台'),
  push_summary: z.boolean(),
  push_time: z.string().regex(/^\d{2}:\d{2}$/, '格式 HH:MM'),
  alert_negative: z.boolean(),
  monitor_frequency: z.number().min(5).max(1440),
  start_time: z.string().regex(/^\d{2}:\d{2}$/, '格式 HH:MM'),
});

type FormValues = z.infer<typeof schema>;

const allPlatforms = [
  { id: 'wb', name: '微博' },
  { id: 'xhs', name: '小红书' },
  { id: 'bili', name: 'B站' },
  { id: 'zhihu', name: '知乎' },
  { id: 'dy', name: '抖音' },
  { id: 'ks', name: '快手' },
  { id: 'tieba', name: '百度贴吧' },
];

export default function SystemSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['system-settings'],
    queryFn: () => radarApi.settings(),
  });

  const [keywordDraft, setKeywordDraft] = useState('');
  const [inactiveDraft, setInactiveDraft] = useState('');

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: data as FormValues | undefined,
  });

  const save = useMutation({
    mutationFn: (v: FormValues) => radarApi.saveSettings(v as SystemSettings),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['system-settings'] });
      toast.success('系统设置已保存');
    },
  });

  const schedulerStart = useMutation({ mutationFn: () => radarApi.schedulerStart(), onSuccess: () => toast.success('调度器已启动') });
  const schedulerStop = useMutation({ mutationFn: () => radarApi.schedulerStop(), onSuccess: () => toast.success('调度器已停止') });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-60 w-full" />
      </div>
    );
  }

  const watched = form.watch();
  const keywords = watched.keywords ?? [];
  const inactive = watched.inactive_keywords ?? [];
  const platforms = watched.platforms ?? [];

  const addKeyword = () => {
    if (!keywordDraft.trim()) return;
    if (keywords.includes(keywordDraft.trim())) {
      toast.warning('关键词已存在');
      return;
    }
    form.setValue('keywords', [...keywords, keywordDraft.trim()], { shouldValidate: true });
    setKeywordDraft('');
  };
  const removeKeyword = (k: string) => form.setValue('keywords', keywords.filter((x) => x !== k), { shouldValidate: true });

  const addInactive = () => {
    if (!inactiveDraft.trim()) return;
    form.setValue('inactive_keywords', [...inactive, inactiveDraft.trim()], { shouldValidate: true });
    setInactiveDraft('');
  };
  const removeInactive = (k: string) => form.setValue('inactive_keywords', inactive.filter((x) => x !== k), { shouldValidate: true });

  const togglePlatform = (id: string) => {
    if (platforms.includes(id)) {
      form.setValue('platforms', platforms.filter((x) => x !== id), { shouldValidate: true });
    } else {
      form.setValue('platforms', [...platforms, id], { shouldValidate: true });
    }
  };

  return (
    <div className="space-y-4">
      {/* AI 助手提示 */}
      <div className="rounded-lg border border-primary/20 bg-primary/[0.03] px-4 py-3 text-xs text-muted-foreground">
        推荐使用{' '}
        <a href="/agent" className="font-medium text-primary hover:underline">AI 助手</a>
        {' '}完成日常操作——管理订阅、触发扫描、查看话题、配置推送更便捷。
      </div>

      <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="space-y-6">
      {/* Scheduler controls */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">调度器</CardTitle>
          <CardDescription>启动或停止 APScheduler，控制自动扫描与每日简报</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button type="button" onClick={() => schedulerStart.mutate()} disabled={schedulerStart.isPending}>
            <Power className="mr-2 h-4 w-4" /> 启动调度器
          </Button>
          <Button type="button" variant="outline" onClick={() => schedulerStop.mutate()} disabled={schedulerStop.isPending}>
            <PowerOff className="mr-2 h-4 w-4" /> 停止调度器
          </Button>
        </CardContent>
      </Card>

      {/* Keywords */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">监控关键词</CardTitle>
          <CardDescription>需要重点关注的核心实体（品牌 / 产品 / 高管）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              value={keywordDraft}
              onChange={(e) => setKeywordDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
              placeholder="输入关键词后回车"
            />
            <Button type="button" onClick={addKeyword} variant="outline">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {keywords.map((k) => (
              <Badge key={k} variant="secondary" className="gap-1 pl-3 pr-1.5">
                {k}
                <button type="button" onClick={() => removeKeyword(k)} className="ml-1 rounded p-0.5 hover:bg-destructive/20">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
            {keywords.length === 0 && <span className="text-xs text-muted-foreground">暂无</span>}
          </div>
          {form.formState.errors.keywords && (
            <p className="text-xs text-destructive">{form.formState.errors.keywords.message}</p>
          )}

          <Separator className="my-4" />

          <Label className="text-sm text-muted-foreground">停用关键词（仅记录不预警）</Label>
          <div className="flex gap-2">
            <Input
              value={inactiveDraft}
              onChange={(e) => setInactiveDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addInactive())}
              placeholder="输入停用关键词后回车"
            />
            <Button type="button" onClick={addInactive} variant="outline">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {inactive.map((k) => (
              <Badge key={k} variant="outline" className="gap-1 pl-3 pr-1.5 opacity-60">
                {k}
                <button type="button" onClick={() => removeInactive(k)} className="ml-1 rounded p-0.5 hover:bg-destructive/20">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Platforms */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">监控平台</CardTitle>
          <CardDescription>选择需要采集的平台</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {allPlatforms.map((p) => {
              const checked = platforms.includes(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => togglePlatform(p.id)}
                  className={
                    'rounded-lg border px-3 py-2.5 text-sm font-medium transition-all ' +
                    (checked
                      ? 'border-primary/40 bg-primary/10 text-primary'
                      : 'border-border bg-muted/30 text-muted-foreground hover:bg-accent')
                  }
                >
                  {p.name}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Frequency & Schedule */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">调度参数</CardTitle>
          <CardDescription>扫描频率与每日简报推送时间</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>扫描频率（分钟）</Label>
            <Input
              type="number"
              min={5}
              max={1440}
              {...form.register('monitor_frequency', { valueAsNumber: true })}
            />
          </div>
          <div className="space-y-2">
            <Label>扫描起始时间</Label>
            <Input type="time" {...form.register('start_time')} />
          </div>
          <div className="space-y-2">
            <Label>每日简报推送时间</Label>
            <Input type="time" {...form.register('push_time')} />
          </div>
          <div className="flex flex-col gap-3 pt-2">
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <Label className="text-sm">每日简报推送</Label>
                <p className="text-xs text-muted-foreground">开启后每日定时汇总</p>
              </div>
              <Switch
                checked={watched.push_summary}
                onCheckedChange={(v) => form.setValue('push_summary', v)}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <Label className="text-sm">负面舆情即时告警</Label>
                <p className="text-xs text-muted-foreground">触发后立即推送</p>
              </div>
              <Switch
                checked={watched.alert_negative}
                onCheckedChange={(v) => form.setValue('alert_negative', v)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={save.isPending} className="gap-2">
          {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          保存设置
        </Button>
      </div>
    </form>
    </div>
  );
}
