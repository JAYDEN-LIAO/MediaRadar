'use client';

import { useState, Suspense } from 'react';
import { Radar, Loader2, Mail, Lock, User } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { authApi } from '@/lib/api';
import { toast } from 'sonner';

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const redirect = params.get('redirect') ?? '/dashboard';
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [nickname, setNickname] = useState('');
  const [pending, setPending] = useState<string | null>(null);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { toast.error('邮箱和密码不能为空'); return; }
    setPending('email');
    try {
      const res = mode === 'login'
        ? await authApi.login(email, password)
        : await authApi.register(email, password, nickname || email.split('@')[0]);
      localStorage.setItem('mediaradar_token', res.token);
      toast.success(mode === 'login' ? '登录成功' : '注册成功');
      router.replace(redirect);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || (mode === 'login' ? '邮箱或密码错误' : '注册失败，邮箱可能已被使用');
      toast.error(msg);
    } finally {
      setPending(null);
    }
  };

  const handleGoogleLogin = async () => {
    setPending('google');
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
      window.location.href = `${base}/api/auth/oauth/google/login?redirect=${encodeURIComponent(redirect)}`;
    } catch {
      toast.error('登录失败');
      setPending(null);
    }
  };

  return (
    <div className="login-grid relative grid min-h-screen w-full place-items-center overflow-hidden bg-background px-4">
      <div className="relative z-10 w-full max-w-sm">
        <Card className="border-border/50 shadow-lg">
          <CardContent className="space-y-5 p-8">
            {/* Brand */}
            <div className="flex flex-col items-center gap-3 text-center">
              <div className="grid h-12 w-12 place-items-center rounded-xl bg-primary text-primary-foreground">
                <Radar className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-foreground">MediaRadar</h1>
                <p className="mt-0.5 text-sm text-muted-foreground">智能舆情监控</p>
              </div>
            </div>

            {/* Email/Password form */}
            <form onSubmit={handleEmailAuth} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs text-muted-foreground/70">邮箱</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40" />
                  <Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)}
                    placeholder="your@email.com" className="pl-9" autoComplete="email" />
                </div>
              </div>
              {mode === 'register' && (
                <div className="space-y-1.5">
                  <Label htmlFor="nickname" className="text-xs text-muted-foreground/70">昵称（可选）</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40" />
                    <Input id="nickname" value={nickname} onChange={e => setNickname(e.target.value)}
                      placeholder="你的昵称" className="pl-9" />
                  </div>
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs text-muted-foreground/70">密码</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40" />
                  <Input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)}
                    placeholder={mode === 'register' ? '至少 6 位' : '输入密码'} className="pl-9" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={pending !== null}>
                {pending === 'email' ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {mode === 'login' ? '登录' : '注册'}
              </Button>
            </form>

            {/* Toggle mode */}
            <div className="text-center">
              <button type="button" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
                className="text-xs text-muted-foreground/60 hover:text-foreground transition-colors">
                {mode === 'login' ? '没有账号？注册' : '已有账号？登录'}
              </button>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 border-t border-border/50" />
              <span className="text-[10px] text-muted-foreground/40 uppercase tracking-wide">或</span>
              <div className="flex-1 border-t border-border/50" />
            </div>

            {/* Google OAuth */}
            <div className="space-y-2.5">
              <Button variant="outline" size="lg" className="w-full gap-3"
                onClick={handleGoogleLogin} disabled={pending !== null}>
                {pending === 'google' ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon className="h-4 w-4" />}
                Google 账号登录
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="grid min-h-screen place-items-center bg-background text-sm text-muted-foreground/60">加载中…</div>}>
      <LoginForm />
    </Suspense>
  );
}
