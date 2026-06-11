'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth-client';

export default function RootIndexPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isAuthenticated() ? '/agent' : '/login');
  }, [router]);
  return (
    <div className="grid min-h-screen place-items-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
    </div>
  );
}
