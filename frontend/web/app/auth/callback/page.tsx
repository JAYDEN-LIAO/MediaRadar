'use client';

import { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get('token');
    const redirect = params.get('redirect') ?? '/dashboard';

    if (token) {
      localStorage.setItem('mediaradar_token', token);
    }

    const timer = setTimeout(() => router.replace(redirect), 200);
    return () => clearTimeout(timer);
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
