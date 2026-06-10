'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Cpu, Save, TestTube, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { llmApi, type LLMConfigItem } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const ROLE_TONE: Record<string, string> = {
  default: 'border-indigo-500/40 bg-indigo-500/10 text-indigo-400',
  analyst: 'border-rose-500/40 bg-rose-500/10 text-rose-400',
  reviewer: 'border-amber-500/40 bg-amber-500/10 text-amber-400',
  embedding: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
  vision: 'border-violet-500/40 bg-violet-500/10 text-violet-400',
};

export default function LLMSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['llm-configs'], queryFn: () => llmApi.configs() });
  const [revealKey, setRevealKey] = useState<Record<string, boolean>>({});

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Cpu className="h-4 w-4" /> 大模型配置
          </CardTitle>
          <CardDescription>
            支持每个 Agent 角色单独配置模型。未配置时自动回退到「默认模型」。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-32 w-full" />)
          ) : (
            data &&
            Object.entries(data).map(([agent, info]) => (
              <AgentCard
                key={agent}
                agent={agent}
                info={info}
                revealed={!!revealKey[agent]}
                onToggleReveal={() => setRevealKey((r) => ({ ...r, [agent]: !r[agent] }))}
                onSaved={() => qc.invalidateQueries({ queryKey: ['llm-configs'] })}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AgentCard({
  agent,
  info,
  revealed,
  onToggleReveal,
  onSaved,
}: {
  agent: string;
  info: LLMConfigItem;
  revealed: boolean;
  onToggleReveal: () => void;
  onSaved: () => void;
}) {
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(info.base_url);
  const [model, setModel] = useState(info.model);

  const save = useMutation({
    mutationFn: () => llmApi.save(agent, { api_key: apiKey || undefined, base_url: baseUrl || undefined, model: model || undefined }),
    onSuccess: (r) => {
      toast.success(r.msg || '配置已保存');
      setApiKey('');
      onSaved();
    },
  });

  const test = useMutation({
    mutationFn: () => llmApi.test(agent),
    onSuccess: (r) => toast.success(r.msg || '连接成功'),
  });

  return (
    <div className="rounded-xl border border-border bg-card/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge variant="outline" className={cn('gap-1.5', ROLE_TONE[agent] ?? '')}>
            <Cpu className="h-3 w-3" />
            {info.label}
          </Badge>
          <span className="text-xs text-muted-foreground">{info.role}</span>
        </div>
        {info.uses_default ? (
          <Badge variant="outline" className="border-zinc-500/40 bg-zinc-500/10 text-zinc-400">
            <AlertCircle className="mr-1 h-3 w-3" /> 使用默认
          </Badge>
        ) : (
          <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-400">
            <CheckCircle2 className="mr-1 h-3 w-3" /> 已配置
          </Badge>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">默认模型</Label>
          <Input value={info.default_model} disabled className="bg-muted/30 text-xs" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">当前生效模型</Label>
          <Input value={info.effective_model || '—'} disabled className="bg-muted/30 text-xs" />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label className="text-xs text-muted-foreground">Base URL</Label>
          <Input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.deepseek.com/v1"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Model</Label>
          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={info.default_model}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">API Key</Label>
          <div className="flex gap-1">
            <Input
              type={revealed ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={info.has_key ? `${info.api_key_masked}（留空保留）` : 'sk-...'}
            />
            <Button type="button" variant="ghost" size="icon" onClick={onToggleReveal}>
              {revealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      <Separator className="my-4" />

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => test.mutate()} disabled={test.isPending}>
          {test.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <TestTube className="mr-2 h-3.5 w-3.5" />}
          测试连接
        </Button>
        <Button type="button" size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-2 h-3.5 w-3.5" />}
          保存
        </Button>
      </div>
    </div>
  );
}
