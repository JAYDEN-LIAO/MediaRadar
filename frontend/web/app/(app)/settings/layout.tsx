'use client';

import { motion } from 'framer-motion';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Radar, Bell, Cpu, User } from 'lucide-react';
import { cn } from '@/lib/utils';

const tabs = [
  { title: '监控设置', href: '/settings/system', icon: Radar },
  { title: '推送设置', href: '/settings/push', icon: Bell },
  { title: '模型设置', href: '/settings/llm', icon: Cpu },
  { title: '账号设置', href: '/settings/account', icon: User },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* 水平标签栏 */}
      <div className="flex gap-1 border-b border-border/60">
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors',
                active
                  ? 'border-foreground text-foreground'
                  : 'border-transparent text-muted-foreground/60 hover:text-foreground hover:border-muted-foreground/20',
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.title}
            </Link>
          );
        })}
      </div>

      {/* 内容区 — 全宽 */}
      <motion.div
        key={pathname}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
      >
        {children}
      </motion.div>
    </div>
  );
}
