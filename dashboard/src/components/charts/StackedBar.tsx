import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts';
import { fmtDate } from '../../lib/format.ts';

interface StackSeries {
  dataKey: string;
  color: string;
  name: string;
}

interface Props {
  data: Record<string, unknown>[];
  series: StackSeries[];
  xKey?: string;
  height?: number;
}

export default function StackedBar({ data, series, xKey = 'day', height = 240 }: Props) {
  if (!data.length) return <p className="text-sm text-text-muted">No data available</p>;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ fontSize: 13 }} labelFormatter={fmtDate} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {series.map(s => (
          <Bar key={s.dataKey} dataKey={s.dataKey} name={s.name} stackId="stack" fill={s.color} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
