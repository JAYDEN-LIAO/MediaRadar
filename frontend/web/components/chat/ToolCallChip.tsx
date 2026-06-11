'use client';

/**
 * ToolCallChip — 工具调用的内联展示芯片
 *
 * 状态：
 *   - pending    │ 圈圈转
 *   - streaming  │ 圈圈转（不同色）
 *   - success    │ √
 *   - error      │ ×
 */
import { Loader2, Check, X, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolCallBlock } from './sse-types';

const TOOL_LABELS: Record<string, string> = {
  // A 组：用户/认证
  whoami: '查询账号',
  list_my_subscriptions: '查询订阅',
  // B 组：订阅
  create_subscription: '创建订阅',
  update_subscription: '修改订阅',
  delete_subscription: '删除订阅',
  pause_subscription: '暂停订阅',
  resume_subscription: '恢复订阅',
  list_subscriptions: '订阅列表',
  // C 组：信息流
  list_recent_topics: '近期话题',
  get_topic_detail: '话题详情',
  list_posts_for_topic: '话题帖子',
  search_posts: '搜索帖子',
  // D 组：推送
  list_push_channels: '推送通道',
  toggle_channel: '切换通道',
  test_channel: '测试推送',
  update_channel_config: '更新推送配置',
  // E 组：模型
  list_models: '模型列表',
  switch_model: '切换模型',
  test_model: '测试模型',
  // F 组：搜索
  web_search: '联网搜索',
  list_search_history: '搜索历史',
  clear_search_cache: '清空搜索缓存',
  // G 组：系统
  get_system_overview: '系统概览',
  health_check: '健康检查',
  get_next_run_time: '下次扫描',
};

interface Props {
  block: ToolCallBlock;
  onClick?: (block: ToolCallBlock) => void;
}

export function ToolCallChip({ block, onClick }: Props) {
  const label = TOOL_LABELS[block.tool] ?? block.tool;
  const isLoading = block.status === 'pending' || block.status === 'streaming';

  return (
    <button
      type="button"
      onClick={() => onClick?.(block)}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
        block.status === 'success' &&
          'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
        block.status === 'error' &&
          'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300',
        isLoading && 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300',
      )}
    >
      {block.status === 'success' && <Check className="h-3 w-3" />}
      {block.status === 'error' && <X className="h-3 w-3" />}
      {isLoading && <Loader2 className="h-3 w-3 animate-spin" />}
      {!isLoading && block.status !== 'success' && block.status !== 'error' && (
        <Wrench className="h-3 w-3" />
      )}
      <span>{label}</span>
    </button>
  );
}
