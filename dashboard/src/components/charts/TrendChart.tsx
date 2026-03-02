import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  LineChart, Line,
} from 'recharts';
import { fmtDate } from '../../lib/format.ts';

interface Series {
  dataKey: string;
  color: string;
  name: string;
  type?: 'area' | 'line';
}

interface Props {
  data: Record<string, unknown>[];
  series: Series[];
  xKey?: string;
  height?: number;
  domain?: [number | 'auto', number | 'auto'];
  referenceLine?: number;
  referenceLabel?: string;
}

export default function TrendChart({
  data,
  series,
  xKey = 'day',
  height = 240,
  domain,
}: Props) {
  if (!data.length) return <p className="text-sm text-text-muted">No data available</p>;

  const hasArea = series.some(s => s.type !== 'line');

  if (!hasArea) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} domain={domain} />
          <Tooltip contentStyle={{ fontSize: 13 }} labelFormatter={fmtDate} />
          {series.map(s => (
            <Line key={s.dataKey} type="monotone" dataKey={s.dataKey} name={s.name} stroke={s.color} strokeWidth={2} dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <defs>
          {series.map(s => (
            <linearGradient key={s.dataKey} id={`grad-${s.dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} domain={domain} />
        <Tooltip contentStyle={{ fontSize: 13 }} labelFormatter={fmtDate} />
        {series.map(s =>
          s.type === 'line' ? (
            <Line key={s.dataKey} type="monotone" dataKey={s.dataKey} name={s.name} stroke={s.color} strokeWidth={2} dot={false} />
          ) : (
            <Area key={s.dataKey} type="monotone" dataKey={s.dataKey} name={s.name} stroke={s.color} strokeWidth={2} fill={`url(#grad-${s.dataKey})`} dot={false} />
          )
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
