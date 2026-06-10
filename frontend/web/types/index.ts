// =========================================================================
// MediaRadar Web — 通用 TypeScript 类型
// =========================================================================

export type Sentiment = 'positive' | 'neutral' | 'negative';
export type RiskLevel = 1 | 2 | 3 | 4 | 5;
export type AlertRecommendation = 'high' | 'medium' | 'low' | 'none';

export interface User {
  id: string;
  name: string;
  email: string;
  image?: string;
  provider: string;
}

export interface NavItem {
  title: string;
  href: string;
  icon: string; // lucide icon name
  description?: string;
}
