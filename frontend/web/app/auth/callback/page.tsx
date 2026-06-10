'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get('token');
    const roleFromUrl = params.get('role');
    const redirect = params.get('redirect') ?? '/dashboard';

    const writeCookies = (role: string) => {
      const maxAge = 'max-age=86400; path=/; SameSite=Lax';
      document.cookie = `mediaradar_token_cookie=${encodeURIComponent(token!)}; ${maxAge}`;
      document.cookie = `mediaradar_role=${encodeURIComponent(role)}; ${maxAge}`;
      localStorage.setItem('mediaradar_token', token!);
    };

    if (token) {
      if (roleFromUrl) {
        writeCookies(roleFromUrl);
        const timer = setTimeout(() => router.replace(redirect), 200);
        return () => clearTimeout(timer);
      }
      // 没传 role：先写默认 user，然后用 me 拉真实 role 覆盖
      writeCookies('user');
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
      fetch(`${apiBase}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(j => {
          if (j?.data?.role) {
            document.cookie = `mediaradar_role=${encodeURIComponent(j.data.role)}; path=/; max-age=86400; SameSite=Lax`;
          }
        })
        .catch(() => { /* 保留默认 user，登录后再调 me 修正 */ })
        .finally(() => {
          const timer = setTimeout(() => router.replace(redirect), 200);
          return () => clearTimeout(timer);
        });
    } else {
      const timer = setTimeout(() => router.replace(redirect), 200);
      return () => clearTimeout(timer);
    }
  }, [router, params]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground/60">登录成功，正在跳转…</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground/60">加载中…</p>
      </div>
    }>
      <CallbackInner />
    </Suspense>
  );
}
