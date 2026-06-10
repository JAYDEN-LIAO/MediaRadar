import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Gauge, Activity, AlertCircle } from 'lucide-react';

export default function AdminHomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">管理总览</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          MediaRadar v2.2 · 多用户 SaaS · 订阅平台
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">注册用户</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">—</div>
            <p className="mt-1 text-xs text-muted-foreground/60">查看用户管理</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">活跃订阅</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">—</div>
            <p className="mt-1 text-xs text-muted-foreground/60">跨用户汇总</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">配额策略</CardTitle>
            <Gauge className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">默认 20</div>
            <p className="mt-1 text-xs text-muted-foreground/60">订阅上限</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">系统状态</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-emerald-600">正常</div>
            <p className="mt-1 text-xs text-muted-foreground/60">P0 阶段就绪</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>下一步</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>· P0 阶段已完成：用户/订阅/模型配置/配额/Admin 后端 + 路由保护</p>
          <p>· P1 待做：26 个 Agent 工具迁移到 <code className="rounded bg-muted px-1.5 py-0.5 text-xs">tools/</code> 包</p>
          <p>· P2 待做：SSE 协议升级（text/tool_call/tool_progress/tool_result/done）</p>
          <p>· P3 待做：前端 Chat 主页 + 右侧数据看板</p>
        </CardContent>
      </Card>
    </div>
  );
}
