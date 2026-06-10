'use client';

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import type { VolumeStats } from '@/lib/api';

// 多关键词配色 — 同一色系不同灰度
const KW_COLORS = ['#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff'];
const NEG_COLOR = '#f43f5e';

interface VolumeChartProps {
  data: VolumeStats;
}

export function VolumeChart({ data }: VolumeChartProps) {
  // 基础数据：总声量 + 负面
  const chartData = data.days.map((d, i) => ({
    day: d,
    总声量: data.volumes[i] ?? 0,
    负面: data.negative_volumes[i] ?? 0,
    // 每个关键词的数据
    ...Object.fromEntries(
      Object.entries(data.keywords_volumes ?? {}).map(([kw, vols]) => [kw, vols[i] ?? 0]),
    ),
  }));

  const keywords = Object.keys(data.keywords_volumes ?? {});
  const hasKeywords = keywords.length > 0;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={chartData} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={KW_COLORS[0]} stopOpacity={0.3} />
            <stop offset="100%" stopColor={KW_COLORS[0]} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradNeg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={NEG_COLOR} stopOpacity={0.25} />
            <stop offset="100%" stopColor={NEG_COLOR} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 0.06)" />
        <XAxis dataKey="day" tick={{ fill: 'oklch(0.7 0 0)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: 'oklch(0.7 0 0)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{
            backgroundColor: 'oklch(0.13 0.01 280)',
            border: '1px solid oklch(1 0 0 / 8%)',
            borderRadius: 8,
            color: '#fff',
            fontSize: 12,
          }}
        />
        {/* 总声量区域 */}
        <Area type="monotone" dataKey="总声量" stroke={KW_COLORS[0]} strokeWidth={2} fill="url(#gradTotal)" name="总声量" />
        {/* 负面区域 */}
        <Area type="monotone" dataKey="负面" stroke={NEG_COLOR} strokeWidth={2} fill="url(#gradNeg)" name="负面" />
        {/* 各关键词线条（无填充） */}
        {hasKeywords && keywords.map((kw, idx) => (
          <Area
            key={kw}
            type="monotone"
            dataKey={kw}
            stroke={KW_COLORS[Math.min(idx + 1, KW_COLORS.length - 1)]}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            fill="none"
            name={kw}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

interface PieDatum {
  name: string;
  value: number;
  color: string;
}

export function RiskPieChart({ data }: { data: PieDatum[] }) {
  const nonZero = data.filter(d => d.value > 0);
  const safeData = nonZero.length > 0 ? nonZero : [{ name: '暂无数据', value: 1, color: 'oklch(0.3 0 0)' }];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={safeData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={3}>
          {safeData.map((entry) => (
            <Cell key={entry.name} fill={entry.color} stroke="none" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'oklch(0.13 0.01 280)',
            border: '1px solid oklch(1 0 0 / 8%)',
            borderRadius: 8,
            color: '#fff',
            fontSize: 12,
          }}
        />
        <Legend
          iconType="circle"
          wrapperStyle={{ fontSize: 11, color: 'oklch(0.7 0 0)' }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
