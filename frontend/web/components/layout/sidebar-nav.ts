// Sidebar navigation config
import {
  LayoutDashboard,
  ListChecks,
  Bot,
  Settings,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description?: string;
  badge?: string;
}

export const mainNav: NavItem[] = [
  { title: '总览仪表盘', href: '/dashboard', icon: LayoutDashboard, description: '今日舆情速览' },
  { title: '舆情列表', href: '/yq-list', icon: ListChecks, description: '话题与帖子' },
  { title: 'AI 助手', href: '/agent', icon: Bot, description: '智能对话分析' },
];

export const settingsNav: NavItem[] = [
  { title: '系统设置', href: '/settings/system', icon: Settings, description: '监控 / 推送 / 模型 / 账号' },
];
