'use client';

/**
 * FallbackCard —— 未注册卡片类型的兜底渲染。
 * 展示 ui.type + JSON 化的 data，便于前端补卡片前的快速验证。
 */
import { Card } from '@/components/ui/card';
import type { CardProps } from './registry';

export function FallbackCard({ card }: CardProps) {
  return (
    <Card className="my-2 overflow-hidden border-dashed">
      <div className="border-b border-border bg-muted/40 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        {card.ui.type || 'unknown'}
      </div>
      <pre className="max-h-64 overflow-auto p-3 text-[11px] leading-relaxed text-foreground/80">
        {JSON.stringify(card.ui.data ?? card.data ?? {}, null, 2)}
      </pre>
    </Card>
  );
}
