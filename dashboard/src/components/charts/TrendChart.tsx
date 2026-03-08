import { useState, useMemo } from 'react';
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
  showRollingToggle?: boolean;
  rollingWindow?: number;
}

function computeRollingAvg(
  data: Record<string, unknown>[],
  keys: string[],
  window: number,
): Record<string, unknown>[] {
  return data.map((row, i) => {
    const out: Record<string, unknown> = { ...row };
    for (const key of keys) {
      const start = Math.max(0, i - window + 1);
      const slice = data.slice(start, i + 1);
      const vals = slice.map(r => r[key] as number).filter(v => v != null && !isNaN(v));
      out[`${key}_avg`] = vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : null;
    }
    return out;
  });
}

export default function TrendChart({
  data,
  series,
  xKey = 'day',
  height = 240,
  domain,
  showRollingToggle = false,
  rollingWindow = 7,
}: Props) {
  const [showRolling, setShowRolling] = useState(false);

  const chartData = useMemo(() => {
    if (!showRolling || !showRollingToggle) return data;
    return computeRollingAvg(data, series.map(s => s.dataKey), rollingWindow);
  }, [data, series, showRolling, showRollingToggle, rollingWindow]);

  if (!data.length) return <p className="text-sm text-text-muted">No data available</p>;

  const allSeries = showRolling && showRollingToggle
    ? [
        ...series,
        ...series.map(s => ({
          dataKey: `${s.dataKey}_avg`,
          color: s.color,
          name: `${s.name} (${rollingWindow}d avg)`,
          type: 'line' as const,
        })),
      ]
    : series;

  const hasArea = allSeries.some(s => s.type !== 'line');
  const isRollingLine = (s: Series) =>
    showRolling && showRollingToggle && s.dataKey.endsWith('_avg');

  const toggle = showRollingToggle && data.length >= rollingWindow ? (
    <div className="flex justify-end mb-1">
      <button
        onClick={() => setShowRolling(v => !v)}
        className={`text-xs px-2 py-0.5 rounded transition-colors ${
          showRolling
            ? 'bg-bg-elevated text-text-primary'
            : 'text-text-muted hover:text-text-secondary'
        }`}
      >
        {rollingWindow}d avg
      </button>
    </div>
  ) : null;

  if (!hasArea) {
    return (
      <div>
        {toggle}
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} domain={domain} />
            <Tooltip contentStyle={{ fontSize: 13 }} labelFormatter={fmtDate} />
            {allSeries.map(s => (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name}
                stroke={s.color}
                strokeWidth={isRollingLine(s) ? 3 : 1.5}
                strokeOpacity={isRollingLine(s) ? 1 : 0.4}
                dot={false}
                strokeDasharray={isRollingLine(s) ? undefined : undefined}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div>
      {toggle}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            {allSeries.map(s => (
              <linearGradient key={s.dataKey} id={`grad-${s.dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <XAxis dataKey={xKey} tickFormatter={fmtDate} tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: '#71717A' }} axisLine={false} tickLine={false} domain={domain} />
          <Tooltip contentStyle={{ fontSize: 13 }} labelFormatter={fmtDate} />
          {allSeries.map(s =>
            s.type === 'line' || isRollingLine(s) ? (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name}
                stroke={s.color}
                strokeWidth={isRollingLine(s) ? 3 : 2}
                strokeOpacity={showRolling && showRollingToggle && !isRollingLine(s) ? 0.4 : 1}
                dot={false}
              />
            ) : (
              <Area
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                strokeOpacity={showRolling && showRollingToggle ? 0.4 : 1}
                fill={`url(#grad-${s.dataKey})`}
                fillOpacity={showRolling && showRollingToggle ? 0.3 : 1}
                dot={false}
              />
            )
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
