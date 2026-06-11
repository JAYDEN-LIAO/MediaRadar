'use client';

/** SearchHistoryListCard —— 搜索历史列表（list_search_history） */
import { Card } from '@/components/ui/card';
import { Search, Clock } from 'lucide-react';
import type { CardProps } from './registry';

export function SearchHistoryListCard({ card }: CardProps) {
  const raw = (card.ui?.data ?? card.data ?? {}) as {
    items?: { query?: string; timestamp?: string; result_count?: number }[];
  };
  const items = raw.items ?? [];

  if (items.length === 0) {
    return (
      <Card className="my-2 p-4 text-center text-xs text-muted-foreground">
        暂无搜索历史
      </Card>
    );
  }

  return (
    <Card className="my-2 overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        本会话搜索记录
      </div>
      <ul className="divide-y divide-border">
        {items.slice(0, 10).map((it, i) => (
          <li key={i} className="flex items-center gap-2 px-3 py-2">
            <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="min-w-0 flex-1 truncate text-xs">{it.query}</span>
            {it.result_count !== undefined && (
              <span className="shrink-0 text-[10px] text-muted-foreground">
                {it.result_count} 条
              </span>
            )}
            {it.timestamp && (
              <span className="shrink-0 text-[10px] text-muted-foreground/70">
                <Clock className="mr-0.5 inline h-2.5 w-2.5" />
                {it.timestamp.slice(5, 16)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
