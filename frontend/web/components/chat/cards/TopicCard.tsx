'use client';

/**
 * TopicCard —— 话题详情（v2 核心卡片）。
 *
 * data: {
 *   topic_id, title, summary,
 *   risk_level, platforms, post_count,
 *   posts: [{ platform, content, published_at, url }],
 *   timeline: [{ date, event }],
 * }
 */
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TrendingUp, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CardProps } from './registry';

interface PostItem {
  platform?: string;
  content?: string;
  published_at?: string;
  url?: string;
}

interface TimelineEvent {
  date?: string;
  event?: string;
}

interface TopicData {
  topic_id?: string;
  title?: string;
  summary?: string;
  risk_level?: number;
  platforms?: string[];
  post_count?: number;
  posts?: PostItem[];
  timeline?: TimelineEvent[];
}

const RISK_TONE: Record<string, string> = {
  high: 'text-rose-600 bg-rose-500/15',
  medium: 'text-amber-600 bg-amber-500/15',
  low: 'text-emerald-600 bg-emerald-500/15',
};

export function TopicCard({ card }: CardProps) {
  const d = (card.ui?.data ?? card.data ?? {}) as TopicData;
  const [showPosts, setShowPosts] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);

  const riskKey = d.risk_level !== undefined
    ? (d.risk_level >= 4 ? 'high' : d.risk_level >= 2 ? 'medium' : 'low')
    : 'low';

  return (
    <Card className="my-2 overflow-hidden">
      {/* 头部 */}
      <div className="flex items-start gap-3 border-b border-border bg-muted/20 p-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          <TrendingUp className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{d.title ?? '(无标题话题)'}</span>
            {d.risk_level !== undefined && (
              <Badge
                variant="outline"
                className={cn('text-[10px]', RISK_TONE[riskKey])}
              >
                Lv.{d.risk_level}
              </Badge>
            )}
          </div>
          {d.summary && (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{d.summary}</p>
          )}
          <div className="mt-1.5 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
            {d.platforms && d.platforms.length > 0 && (
              <span>{d.platforms.join(' / ')}</span>
            )}
            {d.post_count !== undefined && <span>{d.post_count} 条相关</span>}
          </div>
        </div>
      </div>

      {/* 时间线 */}
      {d.timeline && d.timeline.length > 0 && (
        <div className="border-b border-border">
          <button
            type="button"
            onClick={() => setShowTimeline((v) => !v)}
            className="flex w-full items-center gap-1 px-3 py-1.5 text-[11px] font-medium text-muted-foreground hover:bg-muted/30"
          >
            {showTimeline ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            时间线
          </button>
          {showTimeline && (
            <div className="border-t border-border bg-muted/20 px-3 py-2">
              {d.timeline.map((t, i) => (
                <div key={i} className="flex gap-2 py-1 text-[11px]">
                  <span className="shrink-0 font-medium tabular-nums text-muted-foreground">
                    {t.date ?? ''}
                  </span>
                  <span>{t.event ?? ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 相关帖子 */}
      {d.posts && d.posts.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowPosts((v) => !v)}
            className="flex w-full items-center gap-1 px-3 py-1.5 text-[11px] font-medium text-muted-foreground hover:bg-muted/30"
          >
            {showPosts ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            帖子 · {d.posts.length}
          </button>
          {showPosts && (
            <div className="border-t border-border divide-y divide-border">
              {d.posts.slice(0, 20).map((p, i) => (
                <div key={i} className="px-3 py-2">
                  <div className="flex items-start gap-2">
                    <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[9px] font-medium text-muted-foreground">
                      {p.platform ?? 'web'}
                    </span>
                    <p className="min-w-0 flex-1 text-[11px] leading-relaxed">
                      {p.content ?? '(无内容)'}
                    </p>
                    {p.url && (
                      <a href={p.url} target="_blank" rel="noreferrer" className="shrink-0 text-muted-foreground hover:text-primary">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {p.published_at && (
                    <div className="mt-0.5 text-[9px] text-muted-foreground/70">
                      {p.published_at.slice(0, 16)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
