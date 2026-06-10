'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { mainNav, settingsNav } from './sidebar-nav';
import { cn } from '@/lib/utils';
import { useSidebarStore } from '@/stores/sidebar-store';
import { ChevronLeft, Radar } from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { collapsed, toggle } = useSidebarStore();

  return (
    <aside
      className={cn(
        'relative hidden h-screen shrink-0 flex-col border-r border-border/60 bg-sidebar transition-[width] duration-200 ease-out will-change-[width] md:flex',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Brand */}
      <div className={cn('flex h-16 items-center border-b border-border/50', collapsed ? 'justify-center px-2' : 'gap-3 px-4')}>
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[oklch(0.5_0.15_285)] text-white">
          <Radar className="h-4 w-4" />
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex flex-col leading-none"
          >
            <span className="text-sm font-bold tracking-tight">MediaRadar</span>
            <span className="text-[10px] text-muted-foreground/70">舆情雷达 v2.0</span>
          </motion.div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {!collapsed && (
          <p className="mb-2 px-2 text-[9px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50">
            导航
          </p>
        )}
        <ul className="space-y-0.5">
          {mainNav.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
                    active
                      ? 'bg-[oklch(0.5_0.12_285/0.2)] text-foreground'
                      : 'text-muted-foreground/70 hover:bg-[oklch(0.5_0.12_285/0.1)] hover:text-foreground',
                  )}
                >
                  <item.icon
                    className={cn(
                      'h-4 w-4 shrink-0 transition-colors duration-150',
                      active ? 'text-foreground' : 'text-muted-foreground/60 group-hover:text-foreground',
                    )}
                  />
                  {!collapsed && <span className="truncate">{item.title}</span>}
                  {active && !collapsed && (
                    <span className="ml-auto h-1 w-1 rounded-full bg-foreground/30" />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>

        {!collapsed && (
          <p className="mb-2 mt-6 px-2 text-[9px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50">
            设置
          </p>
        )}
        <ul className="space-y-0.5">
          {settingsNav.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
                    active
                      ? 'bg-[oklch(0.5_0.12_285/0.2)] text-foreground'
                      : 'text-muted-foreground/70 hover:bg-[oklch(0.5_0.12_285/0.1)] hover:text-foreground',
                  )}
                >
                  <item.icon
                    className={cn(
                      'h-4 w-4 shrink-0 transition-colors duration-150',
                      active ? 'text-foreground' : 'text-muted-foreground/60 group-hover:text-foreground',
                    )}
                  />
                  {!collapsed && <span className="truncate">{item.title}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <button
        onClick={toggle}
        className={cn(
          'absolute top-20 grid h-6 w-6 place-items-center rounded-full border border-border/60 bg-background text-muted-foreground/60 shadow-sm transition-all hover:text-foreground hover:shadow-md',
          collapsed ? '-right-3' : '-right-3',
        )}
        aria-label="Toggle sidebar"
      >
        <ChevronLeft
          className={cn('h-3.5 w-3.5 transition-transform duration-200', collapsed && 'rotate-180')}
        />
      </button>
    </aside>
  );
}
