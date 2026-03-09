import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ZAxis,
} from 'recharts';
import Badge from '../ui/Badge.tsx';

interface Props {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  xLabel: string;
  yLabel: string;
  rValue: number | null;
  strength: string;
  color?: string;
  height?: number;
}

export default function ScatterPlot({
  data,
  xKey,
  yKey,
  xLabel,
  yLabel,
  rValue,
  strength,
  color = '#C9A96E',
  height = 220,
}: Props) {
  if (!data.length) return <p className="text-sm text-text-muted">No data available</p>;

  const variant = strength === 'strong' ? 'high' : strength === 'moderate' ? 'medium' : 'low';

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Badge label={rValue != null ? `r = ${rValue.toFixed(2)}` : 'N/A'} variant={variant} />
        <Badge label={strength} variant={variant} />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 4, right: 4, bottom: 4, left: -10 }}>
          <XAxis
            dataKey={xKey}
            name={xLabel}
            type="number"
            tick={{ fontSize: 11, fill: '#6B6560' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            dataKey={yKey}
            name={yLabel}
            type="number"
            tick={{ fontSize: 11, fill: '#6B6560' }}
            axisLine={false}
            tickLine={false}
          />
          <ZAxis range={[30, 30]} />
          <Tooltip
            contentStyle={{ fontSize: 12, fontFamily: 'Outfit, sans-serif' }}
            formatter={(val: number | undefined) => val?.toFixed?.(1) ?? String(val)}
          />
          <Scatter data={data} fill={color} fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="text-xs text-text-muted mt-1">{xLabel} vs {yLabel}</p>
    </div>
  );
}
