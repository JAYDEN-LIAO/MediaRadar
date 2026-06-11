'use client';

/**
 * PushChannelListCard —— 推送通道列表
 *
 * data: { items: [{ channel: 'email'|'wecom'|'feishu', enabled, configured, ... }] }
 */
import { Card } from '@/components/ui/card';
import { Mail, MessageCircle, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface ChannelItem {
  channel?: string;
  enabled?: boolean;
  configured?: boolean;
  last_test?: string;
}

const ICON: Record<string, typeof Mail> = {
  email: Mail,
  wecom: MessageCircle,
  feishu: Bot,
};

const LABEL: Record<string, string> = {
  email: '邮箱',
  wecom: '企业微信',
  feishu: '飞书',
};

export function PushChannelListCard({ card }: CardProps) {
  const raw = (card.ui.data ?? card.data ?? {}) as { items?: ChannelItem[] };
  const items = raw.items ?? [];

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        推送通道
      </div>
      <ul className="grid grid-cols-1 gap-1 p-2 sm:grid-cols-3">
        {items.map((it, i) => {
          const Icon = ICON[it.channel ?? ''] ?? Mail;
          const label = LABEL[it.channel ?? ''] ?? it.channel ?? '通道';
          return (
            <li
              key={it.channel ?? i}
              className={cn(
                'flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2',
                it.enabled && 'border-primary/30 bg-primary/5',
              )}
            >
              <Icon className="h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{label}</div>
                <div className="text-[10px] text-muted-foreground">
                  {it.enabled ? '已启用' : '未启用'}
                  {it.configured ? '' : ' · 未配置'}
                </div>
              </div>
              <span
                className={cn(
                  'h-2 w-2 shrink-0 rounded-full',
                  it.enabled ? 'bg-emerald-500' : 'bg-muted-foreground/40',
                )}
              />
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
