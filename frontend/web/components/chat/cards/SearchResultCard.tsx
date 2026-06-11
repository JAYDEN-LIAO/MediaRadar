'use client';

/**
 * SearchResultCard —— 联网搜索结果
 *
 * data: { query, items: [{ title, url, snippet, source }] }
 */
import { Card } from '@/components/ui/card';
import { Search, ExternalLink } from 'lucide-react';
import type { CardProps } from './registry';

interface SearchItem {
  title?: string;
  url?: string;
  snippet?: string;
  source?: string;
}

export function SearchResultCard({ card }: CardProps) {
  const raw = (card.ui.data ?? card.data ?? {}) as {
    query?: string;
    items?: SearchItem[];
  };
  const items = raw.items ?? [];

  return (
    <Card className="my-2 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
        <Search className="h-3 w-3 text-muted-foreground" />
        <span className="text-xs font-medium text-muted-foreground">
          搜索：{raw.query ?? '—'} · {items.length} 条
        </span>
      </div>
      {items.length === 0 ? (
        <div className="p-4 text-center text-sm text-muted-foreground">
          暂无结果
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {items.slice(0, 8).map((it, i) => (
            <li key={i} className="px-3 py-2">
              <a
                href={it.url ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="group block"
              >
                <div className="flex items-center gap-1 text-sm font-medium text-foreground group-hover:text-primary">
                  <span className="truncate">{it.title ?? it.url}</span>
                  <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
                {it.snippet && (
                  <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                    {it.snippet}
                  </p>
                )}
                {it.source && (
                  <p className="mt-0.5 text-[10px] text-muted-foreground/70">
                    {it.source}
                  </p>
                )}
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
