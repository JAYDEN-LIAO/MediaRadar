'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { Users, Gauge, ArrowLeft, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const NAV = [
  { href: '/admin', label: '总览', icon: ShieldCheck },
  { href: '/admin/users', label: '用户管理', icon: Users },
  { href: '/admin/quota', label: '配额调整', icon: Gauge },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // 客户端二次确认：cookie 可能在中间被改（防御 middleware 漏判的边界场景）
    const role = typeof document !== 'undefined'
      ? document.cookie.split('; ').find(c => c.startsWith('mediaradar_role='))?.split('=')[1]
      : null;
    if (role !== 'admin') {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    } else {
      setChecking(false);
    }
  }, [router, pathname]);

  if (checking) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground/20 border-t-muted-foreground/60" />
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Admin 侧边栏 */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-border/50 bg-muted/20">
        <div className="flex h-14 items-center border-b border-border/50 px-4">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">Admin Console</div>
              <div className="text-[10px] text-muted-foreground/60">MediaRadar v2.2</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV.map(item => {
            const active = item.href === '/admin'
              ? pathname === '/admin'
              : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  active
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}>
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border/50 p-3">
          <Button asChild variant="outline" size="sm" className="w-full justify-start">
            <Link href="/dashboard">
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              回到普通视图
            </Link>
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
    </div>
  );
}
