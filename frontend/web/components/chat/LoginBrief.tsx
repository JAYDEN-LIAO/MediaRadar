'use client';

/**
 * LoginBrief —— 登录简报（P5.3）。
 *
 * 展示方式：Chat 欢迎区域替换纯文本，卡片式分项。
 * 数据源：today_summary + scheduler_status API。
 *
 * 布局：
 *   ┌── 今日总览 ──┐
 *   │ 扫描 N 次 ✓   │  高危 0 · 中危 2
 *   │ 新增话题 N    │  推送 3 · 压住 7
 *   └──────────────┘
 *   ┌── 需要关注 ──┐
 *   │ • 小米SU7 ... │
 *   └──────────────┘
 *   [查看话题] [触发扫描]
 */
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { DashboardCards } from './brief/DashboardCards';
import { HotTopics } from './brief/HotTopics';

interface Props {
  onAction?: (msg: string) => void;
}

export function LoginBrief({ onAction }: Props) {
  return (
    <div className="space-y-2">
      <DashboardCards />
      <HotTopics onAction={onAction} />
      {onAction && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => onAction('看看今天有哪些话题')}
          >
            查看话题
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => onAction('触发一次扫描')}
          >
            触发扫描
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => onAction('今天有什么需要关注的')}
          >
            今日全部
          </Button>
        </div>
      )}
    </div>
  );
}
