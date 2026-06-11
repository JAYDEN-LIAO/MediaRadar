'use client';

/** SubscriptionCard —— 单条订阅详情（add / update / remove 结果） */
import { Card } from '@/components/ui/card';
import { Bell, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

const TYPE_LABEL: Record<string, string> = {
  person: '人物', brand: '品牌/产品', event: '事件', industry: '行业', keyword: '关键词',
};
const PUSH_LABEL: Record<string, string> = {
  every: '推每条', important: '重要才推', silent: '静默', off: '关闭',
};

export function SubscriptionCard({ card }: CardProps) {
  const raw = (card.ui?.data ?? card.data ?? {}) as Record<string, unknown>;
  const deleted = !!(raw.deleted || raw.__deleted__);

  if (deleted) {
    return (
      <Card className="my-2 overflow-hidden border-dashed border-rose-500/30 bg-rose-500/5">
        <div className="flex items-center gap-3 p-3">
          <Trash2 className="h-4 w-4 text-rose-500" />
          <div className="text-xs text-muted-foreground">
            已移除订阅：{(raw.name as string) ?? (raw.subscription_id as string) ?? '(无名称)'}
          </div>
        </div>
      </Card>
    );
  }

  const name = raw.name as string | undefined;
  const typeVal = raw.type as string | undefined;
  const pushMode = raw.push_mode as string | undefined;
  const polarity = raw.polarity as string | undefined;
  const freqMin = raw.frequency_min as number | undefined;
  const platformsList = raw.platforms as string[] | undefined;

  return (
    <Card className="my-2 overflow-hidden">
      <div className="flex items-start gap-3 p-3">
        <div
          className={cn(
            'grid h-8 w-8 shrink-0 place-items-center rounded-lg',
            'bg-emerald-500/15 text-emerald-600',
          )}
        >
          <Bell className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{name ?? '(未命名)'}</span>
            <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {TYPE_LABEL[typeVal ?? ''] ?? typeVal ?? '订阅'}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span>推送 · {PUSH_LABEL[pushMode ?? ''] ?? pushMode ?? 'important'}</span>
            <span>极性 · {polarity ?? 'all'}</span>
            <span>频率 · {freqMin ?? 60}min</span>
            {platformsList && platformsList.length > 0 && (
              <span>平台 · {platformsList.join(', ')}</span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
