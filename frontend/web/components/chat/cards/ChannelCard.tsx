'use client';

/** ChannelCard —— 单通道详情（toggle / update_channel_config 结果） */
import { Card } from '@/components/ui/card';
import { Mail, MessageCircle, Bot, Rss } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

const ICONS: Record<string, typeof Mail> = {
  email: Mail, wecom: MessageCircle, feishu: Bot, rss: Rss,
};
const LABELS: Record<string, string> = {
  email: '邮箱', wecom: '企业微信', feishu: '飞书', rss: 'RSS',
};

export function ChannelCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as {
    channel?: string;
    enabled?: boolean;
    configured?: boolean;
    last_test?: string;
  };
  const ch = d.channel ?? '';
  const Icon = ICONS[ch] ?? Mail;

  return (
    <Card className="my-2 p-3">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'grid h-8 w-8 shrink-0 place-items-center rounded-lg',
            d.enabled ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{LABELS[ch] ?? ch}</span>
            <span
              className={cn(
                'rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                d.enabled
                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              {d.enabled ? '已启用' : '未启用'}
            </span>
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {d.configured ? '已配置' : '未配置'}
            {d.last_test && <> · 上次测试 {d.last_test.slice(5, 16)}</>}
          </div>
        </div>
      </div>
    </Card>
  );
}
