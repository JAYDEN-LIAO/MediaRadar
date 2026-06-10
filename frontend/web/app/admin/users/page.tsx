'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { Loader2, Search, ShieldOff } from 'lucide-react';

interface UserItem {
  id: string;
  email: string | null;
  nickname: string;
  role: string;
  is_active: number;
  created_at: string;
  last_login_at: string | null;
}

interface ListResp {
  items: UserItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export default function AdminUsersPage() {
  const router = useRouter();
  const [data, setData] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);

  const load = async (kw: string = keyword, p: number = page) => {
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
      const params = new URLSearchParams({ page: String(p), page_size: '20' });
      if (kw) params.set('keyword', kw);
      const res = await fetch(`${apiBase}/api/admin/users?${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('mediaradar_token')}` },
      });
      const json = await res.json();
      if (json?.data) setData(json.data);
    } catch (e) {
      toast.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    load(keyword, 1);
  };

  const handleDeactivate = async (userId: string) => {
    if (!confirm('确定禁用该用户？')) return;
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8008';
      const res = await fetch(`${apiBase}/api/admin/users/${userId}/deactivate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('mediaradar_token')}` },
      });
      const json = await res.json();
      if (json?.code === 200) {
        toast.success('已禁用');
        load();
      } else {
        toast.error(json?.msg || '禁用失败');
      }
    } catch {
      toast.error('网络错误');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">用户管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data ? `共 ${data.total} 个用户` : '加载中…'}
          </p>
        </div>
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="搜索邮箱/昵称"
            className="w-64"
          />
          <Button type="submit" size="sm" variant="outline">
            <Search className="h-4 w-4" />
          </Button>
        </form>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>用户列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3">邮箱</th>
                    <th className="py-2 pr-3">昵称</th>
                    <th className="py-2 pr-3">角色</th>
                    <th className="py-2 pr-3">状态</th>
                    <th className="py-2 pr-3">注册时间</th>
                    <th className="py-2 pr-3">最后登录</th>
                    <th className="py-2 pr-3">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map(u => (
                    <tr key={u.id} className="border-b border-border/30 last:border-0">
                      <td className="py-2 pr-3 font-mono text-xs">{u.email || '—'}</td>
                      <td className="py-2 pr-3">{u.nickname}</td>
                      <td className="py-2 pr-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          u.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {u.is_active ? '正常' : '已禁用'}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {u.created_at?.slice(0, 10) || '—'}
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {u.last_login_at?.slice(0, 10) || '从未'}
                      </td>
                      <td className="py-2 pr-3">
                        {u.is_active === 1 && (
                          <Button size="sm" variant="ghost" onClick={() => handleDeactivate(u.id)}>
                            <ShieldOff className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data?.items.length === 0 && (
                <div className="py-8 text-center text-sm text-muted-foreground">暂无用户</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {data && data.has_next && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => { const np = page + 1; setPage(np); load(keyword, np); }}>
            加载更多
          </Button>
        </div>
      )}
    </div>
  );
}
