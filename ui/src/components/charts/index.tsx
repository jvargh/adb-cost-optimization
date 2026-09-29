import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART_COLORS, chartColor, formatMoney, formatNumber, humanizeKey } from '@/lib/format';

const AXIS = { stroke: 'var(--text-muted)', fontSize: 11 } as const;
const GRID = { stroke: 'var(--border-subtle)', strokeDasharray: '3 3' } as const;

const tooltipStyle = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-strong)',
  borderRadius: 8,
  fontSize: 12,
  color: 'var(--text-primary)',
} as const;

function compact(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(0)}k`;
  return String(Math.round(value));
}

export interface TrendSeries {
  key: string;
  label: string;
}

export function TrendChart({
  data,
  series,
  currency,
  height = 260,
  xKey = 'date',
}: {
  data: Record<string, string | number>[];
  series: TrendSeries[];
  currency: string;
  height?: number;
  xKey?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          {series.map((s, index) => (
            <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={chartColor(index)} stopOpacity={0.5} />
              <stop offset="95%" stopColor={chartColor(index)} stopOpacity={0.04} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey={xKey} {...AXIS} tickLine={false} minTickGap={24} />
        <YAxis {...AXIS} tickLine={false} axisLine={false} tickFormatter={compact} width={46} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number, name: string) => [formatMoney(value, currency), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, index) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={chartColor(index)}
            fill={`url(#grad-${s.key})`}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function RankedBarChart({
  data,
  currency,
  height = 300,
  onSelect,
}: {
  data: { label: string; value: number; key: string }[];
  currency: string;
  height?: number;
  onSelect?: (key: string) => void;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid {...GRID} horizontal={false} />
        <XAxis type="number" {...AXIS} tickLine={false} axisLine={false} tickFormatter={compact} />
        <YAxis
          type="category"
          dataKey="label"
          {...AXIS}
          width={190}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          cursor={{ fill: 'var(--cp-chart-cursor)' }}
          contentStyle={tooltipStyle}
          formatter={(value: number) => formatMoney(value, currency)}
        />
        <Bar
          dataKey="value"
          radius={[0, 4, 4, 0]}
          onClick={onSelect ? (entry: { key?: string }) => entry.key && onSelect(entry.key) : undefined}
        >
          {data.map((entry, index) => (
            <Cell key={entry.key} fill={chartColor(index)} cursor={onSelect ? 'pointer' : undefined} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function BreakdownChart({
  data,
  currency,
  height = 260,
}: {
  data: { label: string; value: number; key: string }[];
  currency: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="label"
          innerRadius="52%"
          outerRadius="80%"
          paddingAngle={1}
          stroke="var(--bg-surface)"
        >
          {data.map((entry, index) => (
            <Cell key={entry.key} fill={chartColor(index)} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number, name: string) => [formatMoney(value, currency), name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function DistributionChart({
  data,
  height = 220,
  unit = '',
  color = CHART_COLORS[3],
}: {
  data: { label: string; value: number }[];
  height?: number;
  unit?: string;
  color?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="label" {...AXIS} tickLine={false} interval={0} />
        <YAxis {...AXIS} tickLine={false} axisLine={false} width={40} />
        <Tooltip
          cursor={{ fill: 'var(--cp-chart-cursor)' }}
          contentStyle={tooltipStyle}
          formatter={(value: number) => `${formatNumber(value)}${unit}`}
        />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function QualityRadar({
  metrics,
  height = 300,
}: {
  metrics: { metric: string; value: number }[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={metrics} outerRadius="70%" margin={{ top: 16, right: 44, bottom: 16, left: 44 }}>
        <PolarGrid stroke="var(--border-subtle)" />
        <PolarAngleAxis
          dataKey="metric"
          tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
          tickFormatter={(value: string) => humanizeKey(value)}
        />
        <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
        <Radar
          name="Quality"
          dataKey="value"
          stroke={CHART_COLORS[0]}
          fill={CHART_COLORS[0]}
          fillOpacity={0.25}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number) => `${(value * 100).toFixed(0)}%`}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
