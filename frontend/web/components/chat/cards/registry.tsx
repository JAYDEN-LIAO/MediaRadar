'use client';

/**
 * 卡片注册表 —— type → Component 映射。
 *
 * 后端返回 tool_result.ui.type，前端按 type 查找渲染器。
 * 后端 type 命名见 AGENT_REDESIGN.md §7。
 */
import type { ComponentType } from 'react';
import type { UICard } from '../sse-types';
import { FallbackCard } from './FallbackCard';
import { SubscriptionListCard } from './SubscriptionListCard';
import { SubscriptionCard } from './SubscriptionCard';
import { IntentPreviewCard } from './IntentPreviewCard';
import { TopicListCard } from './TopicListCard';
import { TopicCard } from './TopicCard';
import { AlertListCard } from './AlertListCard';
import { StatsChartCard } from './StatsChartCard';
import { PushChannelListCard } from './PushChannelListCard';
import { ChannelCard } from './ChannelCard';
import { TestResultCard } from './TestResultCard';
import { ModelListCard } from './ModelListCard';
import { ModelCard } from './ModelCard';
import { SearchResultCard } from './SearchResultCard';
import { SearchStreamCard } from './SearchStreamCard';
import { SearchHistoryListCard } from './SearchHistoryListCard';
import { SystemOverviewCard } from './SystemOverviewCard';
import { ScanProgressCard } from './ScanProgressCard';
import { ScanStatusCard } from './ScanStatusCard';
import { SchedulerInfoCard } from './SchedulerInfoCard';
import { HealthGridCard } from './HealthGridCard';
import { ActivityTimelineCard } from './ActivityTimelineCard';
import { AckTextCard } from './AckTextCard';

export interface CardProps {
  card: UICard;
}

const REGISTRY: Record<string, ComponentType<CardProps>> = {
  // A — 订阅
  subscription_list: SubscriptionListCard,
  subscription_card: SubscriptionCard,
  subscription_detail: SubscriptionCard,
  subscription_created: SubscriptionCard,
  intent_preview: IntentPreviewCard,

  // B — 扫描
  scan_progress: ScanProgressCard,
  scan_status: ScanStatusCard,
  scheduler_info: SchedulerInfoCard,

  // C — 数据
  topic_list: TopicListCard,
  topic_card: TopicCard,
  topic_detail: TopicCard,
  alert_list: AlertListCard,
  post_list: AlertListCard,
  stats_chart: StatsChartCard,

  // D — 推送
  channel_list: PushChannelListCard,
  channel_card: ChannelCard,
  push_test_result: TestResultCard,

  // E — 模型
  model_list: ModelListCard,
  model_card: ModelCard,
  model_test_result: TestResultCard,

  // F — 搜索
  search_result: SearchResultCard,
  search_stream: SearchStreamCard,
  search_history: SearchHistoryListCard,
  search_history_list: SearchHistoryListCard,

  // G — 系统
  system_overview: SystemOverviewCard,
  health_status: HealthGridCard,
  health_grid: HealthGridCard,
  scheduler_next_run: SchedulerInfoCard,
  activity_timeline: ActivityTimelineCard,

  // 杂项
  account_card: FallbackCard,
  ack_text: AckTextCard,
};

export function renderCard(card: UICard) {
  const Comp = REGISTRY[card.ui.type] ?? FallbackCard;
  return <Comp card={card} />;
}
