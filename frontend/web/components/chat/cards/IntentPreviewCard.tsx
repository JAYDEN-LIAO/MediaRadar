'use client';

/**
 * IntentPreviewCard —— 订阅意图预览 + confirm 卡片。
 * parse_intent 之后、add_subscription 之前展示，等用户确认。
 *
 * 后端数据: {
 *   name, type, type_confidence,
 *   polarity, push_mode, scene,
 *   suggested_platforms, suggested_frequency_min,
 *   raw_input
 * }
 */
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

const TYPE_LABEL: Record<string, string> = {
  person: '人物', brand: '品牌/产品', event: '事件', industry: '行业', keyword: '关键词',
};
const PUSH_LABEL: Record<string, string> = {
  every: '推每条', important: '重要才推', silent: '静默', off: '关闭',
};
const POLARITY_LABEL: Record<string, string> = {
  negative: '负面', positive: '正面', neutral: '中性', all: '全部',
};

interface IntentData {
  name?: string;
  type?: string;
  type_confidence?: number;
  polarity?: string;
  push_mode?: string;
  scene?: string;
  suggested_platforms?: string[];
  suggested_frequency_min?: number;
  raw_input?: string;
}

export function IntentPreviewCard({ card }: CardProps) {
  const [dismissed, setDismissed] = useState(false);
  const d = (card.ui?.data ?? card.data ?? {}) as IntentData;

  if (dismissed) return null;

  const pct = d.type_confidence !== undefined ? Math.round(d.type_confidence * 100) : undefined;

  return (
    <Card className="my-2 overflow-hidden border-primary/30 bg-primary/[0.02]">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          订阅预览
        </span>
      </div>
      <div className="p-3">
        {/* 名称 + 类型 */}
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold">{d.name ?? '(未识别)'}</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
            {TYPE_LABEL[d.type ?? ''] ?? d.type ?? '未知类型'}
          </span>
          {pct !== undefined && (
            <span className="text-[10px] text-muted-foreground">
              {pct}% 确信
            </span>
          )}
        </div>

        {/* 属性 */}
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
          <span>极性 · {POLARITY_LABEL[d.polarity ?? ''] ?? d.polarity ?? '全部'}</span>
          <span>推送 · {PUSH_LABEL[d.push_mode ?? ''] ?? d.push_mode ?? 'important'}</span>
          {d.scene && <span>场景 · {d.scene}</span>}
          {d.suggested_frequency_min && <span>频率 · {d.suggested_frequency_min}min</span>}
          {d.suggested_platforms && d.suggested_platforms.length > 0 && (
            <span>平台 · {d.suggested_platforms.join(', ')}</span>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="mt-3 flex gap-2">
          <Button size="sm" className="h-7 gap-1 text-xs" onClick={() => setDismissed(true)}>
            <Check className="h-3 w-3" />
            确认订阅
          </Button>
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs" onClick={() => setDismissed(true)}>
            <X className="h-3 w-3" />
            修改
          </Button>
        </div>
      </div>
    </Card>
  );
}
