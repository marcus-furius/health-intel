import SparkLine from '../charts/SparkLine.tsx';
import Skeleton from './Skeleton.tsx';
import { fmtNumber, trendArrow, trendColor } from '../../lib/format.ts';
import type { SparkPoint } from '../../lib/api.ts';

interface Props {
  label: string;
  value: number | null;
  unit: string;
  trend: number | null;
  sparkline: SparkPoint[];
  color?: string;
  loading?: boolean;
}

export default function MetricCard({ label, value, unit, trend, sparkline, color = '#3B82F6', loading }: Props) {
  if (loading) {
    return (
      <div className="bg-bg-card border border-border-subtle rounded-xl p-6">
        <Skeleton className="h-4 w-20 mb-3" />
        <Skeleton className="h-10 w-28 mb-3" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  const arrow = trendArrow(trend);
  const arrowColor = trendColor(trend);

  return (
    <div className="bg-bg-card border border-border-subtle rounded-xl p-6 transition-all hover:border-border-default hover:shadow-lg hover:shadow-black/5">
      <p className="text-sm text-text-muted font-medium">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="text-4xl font-semibold tracking-tight">
          {fmtNumber(value, value != null && value % 1 !== 0 ? 1 : 0)}
        </span>
        <span className="text-sm text-text-muted">{unit}</span>
        {arrow && (
          <span className={`text-sm font-medium ${arrowColor}`}>{arrow}</span>
        )}
      </div>
      <div className="mt-3 h-12">
        <SparkLine data={sparkline} color={color} />
      </div>
    </div>
  );
}
