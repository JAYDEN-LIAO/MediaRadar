'use client';

/**
 * SearchStreamCard —— 流式搜索容器（web_search）。
 *
 * 接收增量 tool_progress 推送，逐步追加结果。
 * data.items 是最终聚合完的结果列表。
 */
import { Card } from '@/components/ui/card';
import { Search, ExternalLink, Loader2 } from 'lucide-react';
import type { CardProps } from './registry';

interface SearchItem {
  title?: string;
  snippet?: string;
  url?: string;
  platform?: string;
  publish_time?: string;
  relevance?: number;
}

interface SearchData {
  query?: string;
  total?: number;
  by_platform?: Record<string, number>;
  items?: SearchItem[];
}

export function SearchStreamCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as SearchData;
  const items = d.items ?? [];
  const loading = !d.total && items.length === 0;

  return (
    <Card className="my-2 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
        {loading ? (
          <Loader2 className="h-3 w-3 animate-spin text-primary" />
        ) : (
          <Search className="h-3 w-3 text-muted-foreground" />
        )}
        <span className="text-xs font-medium text-muted-foreground">
          {d.query ? `搜索：${d.query}` : '全网搜索'}
        </span>
        {d.total !== undefined && (
          <span className="ml-auto text-[10px] text-muted-foreground">
            {d.total} 条结果
          </span>
        )}
      </div>

      {d.by_platform && Object.keys(d.by_platform).length > 0 && (
        <div className="flex gap-2 border-b border-border bg-muted/10 px-3 py-1.5 text-[10px] text-muted-foreground">
          {Object.entries(d.by_platform).map(([plat, count]) => (
            <span key={plat}>{plat} {count}</span>
          ))}
        </div>
      )}

      {items.length > 0 ? (
        <ul className="divide-y divide-border">
          {items.slice(0, 15).map((it, i) => (
            <li key={i} className="px-3 py-2">
              <a href={it.url ?? '#'} target="_blank" rel="noreferrer" className="group block">
                <div className="flex items-center gap-1.5">
                  <span className="rounded bg-muted px-1 py-0.5 text-[9px] font-medium text-muted-foreground">
                    {it.platform ?? 'web'}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs font-medium group-hover:text-primary">
                    {it.title ?? '无标题'}
                  </span>
                  <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
                {it.snippet && (
                  <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">{it.snippet}</p>
                )}
                {it.relevance !== undefined && (
                  <span className="mt-0.5 text-[9px] text-muted-foreground/70">
                    相关度 {Math.round(it.relevance * 100)}%
                  </span>
                )}
                {it.publish_time && (
                  <span className="ml-2 text-[9px] text-muted-foreground/70">{it.publish_time.slice(0, 10)}</span>
                )}
              </a>
            </li>
          ))}
        </ul>
      ) : loading ? (
        <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          搜索中…
        </div>
      ) : (
        <div className="p-4 text-center text-xs text-muted-foreground">无结果</div>
      )}
    </Card>
  );
}
