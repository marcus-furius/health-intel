import {
  ResponsiveContainer,
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import { fmtDate } from '../../lib/format.ts';

interface Props {
  data: Record<string, unknown>[];
  dataKey: string;
  color: string;
  xKey?: string;
  height?: number;
  name?: string;
  horizontal?: boolean;
}

export default function BarChart({
  data,
  dataKey,
  color,
  xKey = 'day',
  height = 240,
  name,
  horizontal = false,
}: Props) {
  if (!data.length) return <p className="text-sm text-text-muted">No data available</p>;

  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(height, data.length * 36)}>
        <ReBarChart data={data} layout="vertical" margin={{ top: 0, right: 4, bottom: 0, left: 0 }}>
          <XAxis type="number" tick={{ fontSize: 11, fill: '#6B6560' }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey={xKey} tick={{ fontSize: 11, fill: '#A69F95' }} axisLine={false} tickLine={false} width={100} />
          <Tooltip contentStyle={{ fontSize: 13, fontFamily: 'Outfit, sans-serif' }} />
          <Bar dataKey={dataKey} name={name || dataKey} fill={color} radius={[0, 6, 6, 0]} />
        </ReBarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReBarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#6B6560' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#6B6560' }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ fontSize: 13, fontFamily: 'Outfit, sans-serif' }} labelFormatter={fmtDate} />
        <Bar dataKey={dataKey} name={name || dataKey} fill={color} radius={[6, 6, 0, 0]} />
      </ReBarChart>
    </ResponsiveContainer>
  );
}
