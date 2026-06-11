'use client';

/** AckTextCard —— 纯文本确认卡片（clear_search_cache 等无需 ui 的工具） */
import { Check } from 'lucide-react';
import type { CardProps } from './registry';

export function AckTextCard({ card }: CardProps) {
  return (
    <div className="my-2 flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2.5 text-xs text-emerald-700 dark:text-emerald-300">
      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{(card.ui?.data?.message as string) ?? '操作已执行'}</span>
    </div>
  );
}
