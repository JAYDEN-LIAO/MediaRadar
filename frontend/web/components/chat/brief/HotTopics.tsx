'use client';

/** HotTopics —— 登录简报中的"需要关注"列表 */
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { TrendingUp, ChevronRight } from 'lucide-react';
import { radarApi } from '@/lib/api';

interface Props {
  onAction?: (msg: string) => void;
}

export function HotTopics({ onAction }: Props) {
  const today = useQuery({
    queryKey: ['today-summary'],
    queryFn: () => radarApi.todaySummary(),
    refetchInterval: 60_000,
  });

  const keyword = today.data?.keyword;
  const summary = today.data?.summary;

  if (today.isLoading) {
    return (
      <Card className="overflow-hidden p-3">
        <Skeleton className="h-12 w-full" />
      </Card>
    );
  }

  if (!keyword && !summary) return null;

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-1.5 border-b border-border bg-muted/30 px-3 py-1.5">
        <TrendingUp className="h-3 w-3 text-amber-500" />
        <span className="text-xs font-medium text-muted-foreground">
          需要关注
        </span>
      </div>
      <div className="p-3">
        {keyword && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              <span className="text-sm font-medium">{keyword}</span>
            </div>
            {onAction && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-0.5 text-[10px] text-muted-foreground"
                onClick={() => onAction(`搜一下 ${keyword} 的最新动态`)}
              >
                查看 <ChevronRight className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}
        {summary && (
          <p className="mt-1.5 line-clamp-2 text-[11px] text-muted-foreground">
            {summary}
          </p>
        )}
      </div>
    </Card>
  );
}
