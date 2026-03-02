import { ResponsiveContainer, AreaChart, Area } from 'recharts';
import type { SparkPoint } from '../../lib/api.ts';

interface Props {
  data: SparkPoint[];
  color?: string;
}

export default function SparkLine({ data, color = '#3B82F6' }: Props) {
  const filtered = data.filter(d => d.value != null);
  if (filtered.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={filtered} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#spark-${color.replace('#', '')})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
