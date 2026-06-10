'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef } from 'react';
import { ArrowUpDown, ChevronUp, ChevronDown, Search, Filter } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { radarApi, type TopicListItem } from '@/lib/api';
import { cn } from '@/lib/utils';

const riskBadge: Record<string, string> = {
  高风险: 'text-rose-500',
  中风险: 'text-amber-500',
  低风险: 'text-emerald-500',
  待观察: 'text-muted-foreground/60',
};

export default function YqListPage() {
  const [globalFilter, setGlobalFilter] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState<string>('all');
  const [sorting, setSorting] = useState<SortingState>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['topic-list', sentimentFilter],
    queryFn: () => radarApi.topicList({ sentiment: sentimentFilter === 'all' ? undefined : sentimentFilter }),
    refetchInterval: 10_000,
  });

  const columns = useMemo<ColumnDef<TopicListItem>[]>(
    () => [
      {
        accessorKey: 'topic_name',
        header: '话题',
        cell: ({ row }) => (
          <div className="max-w-[280px]">
            <p className="truncate text-sm font-medium">{row.original.topic_name}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{row.original.cluster_summary}</p>
          </div>
        ),
      },
      {
        accessorKey: 'keyword',
        header: '关键词',
        cell: ({ getValue }) => (
          <Badge variant="outline" className="font-mono text-[10px]">
            {String(getValue())}
          </Badge>
        ),
      },
      {
        id: 'platforms',
        header: '平台',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.platforms.slice(0, 2).map((p) => (
              <span key={p} className="rounded-md bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                {p}
              </span>
            ))}
          </div>
        ),
      },
      {
        accessorKey: 'risk_text',
        header: '风险',
        cell: ({ getValue }) => (
          <Badge variant="outline" className={cn('text-[10px]', riskBadge[String(getValue())] ?? '')}>
            {String(getValue())}
          </Badge>
        ),
      },
      {
        accessorKey: 'post_count',
        header: '声量',
        cell: ({ getValue }) => <span className="font-mono text-sm">{Number(getValue()).toLocaleString()}</span>,
      },
      {
        accessorKey: 'sentiment',
        header: '情感',
        cell: ({ getValue }) => {
          const v = String(getValue());
          const map: Record<string, string> = {
            负面: 'text-rose-400',
            正面: 'text-emerald-400',
            中性: 'text-zinc-400',
          };
          return <span className={cn('text-sm', map[v])}>{v}</span>;
        },
      },
      {
        accessorKey: 'evolution_signal',
        header: '趋势',
        cell: ({ getValue }) => {
          const v = String(getValue());
          const map: Record<string, { label: string; color: string }> = {
            escalating: { label: '升级中', color: 'text-rose-400' },
            stable: { label: '稳定', color: 'text-zinc-400' },
            deescalating: { label: '缓和', color: 'text-emerald-400' },
            unknown: { label: '未知', color: 'text-zinc-500' },
          };
          return <span className={cn('text-xs', map[v]?.color)}>{map[v]?.label ?? v}</span>;
        },
      },
      {
        accessorKey: 'last_seen',
        header: '最后更新',
        cell: ({ getValue }) => {
          const v = String(getValue());
          if (!v) return <span className="text-xs text-muted-foreground">—</span>;
          const d = new Date(v);
          return <span className="text-xs text-muted-foreground">{d.toLocaleString('zh-CN', { hour12: false })}</span>;
        },
      },
    ],
    [],
  );

  const tableData = useMemo(() => {
    if (!data) return [];
    if (!globalFilter) return data;
    const q = globalFilter.toLowerCase();
    return data.filter(
      (t) =>
        t.topic_name.toLowerCase().includes(q) ||
        t.keyword.toLowerCase().includes(q) ||
        (t.cluster_summary ?? '').toLowerCase().includes(q),
    );
  }, [data, globalFilter]);

  const table = useReactTable({
    data: tableData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  // 虚拟滚动
  const containerRef = useRef<HTMLDivElement>(null);
  const rows = table.getRowModel().rows;
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 64,
    overscan: 8,
  });

  return (
    <div className="space-y-6">
      {/* 过滤栏 */}
      <Card>
        <CardContent className="flex flex-col gap-3 py-4 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="搜索话题、关键词…"
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={sentimentFilter} onValueChange={setSentimentFilter}>
            <SelectTrigger className="w-full md:w-[140px]">
              <Filter className="mr-2 h-3.5 w-3.5" />
              <SelectValue placeholder="情感" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="negative">负面</SelectItem>
              <SelectItem value="neutral">中性</SelectItem>
              <SelectItem value="positive">正面</SelectItem>
            </SelectContent>
          </Select>
          <Badge variant="outline" className="ml-auto">
            共 {tableData.length} 条
          </Badge>
        </CardContent>
      </Card>

      {/* 话题列表 */}
      <div ref={containerRef} className="relative max-h-[calc(100vh-340px)] overflow-auto">
        <table className="w-full caption-bottom text-sm">
          <thead className="sticky top-0 z-10 bg-background">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className="h-8 px-3 text-left align-middle text-[11px] font-medium text-muted-foreground/50 uppercase tracking-wider"
                      onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                      style={{ cursor: canSort ? 'pointer' : 'default' }}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {canSort && (
                          sorted === 'asc' ? <ChevronUp className="h-3 w-3" /> :
                          sorted === 'desc' ? <ChevronDown className="h-3 w-3" /> :
                          <ArrowUpDown className="h-3 w-3 opacity-30" />
                        )}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  {columns.map((_, j) => (
                    <td key={j} className="p-3">
                      <Skeleton className="h-6 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-16 text-center text-sm text-muted-foreground/60">
                  没有匹配的话题
                </td>
              </tr>
            ) : (
              <>
                {virtualizer.getVirtualItems().map((virtualRow) => {
                  const row = rows[virtualRow.index];
                  return (
                    <tr
                      key={row.id}
                      className="transition-colors hover:bg-[oklch(0.15_0.03_290/0.06)]"
                      style={{ height: virtualRow.size }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-2.5 align-middle text-[13px] leading-tight">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
