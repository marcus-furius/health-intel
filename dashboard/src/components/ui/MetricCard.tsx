import SparkLine from '../charts/SparkLine.tsx';
import Skeleton from './Skeleton.tsx';
import { fmtNumber, trendArrow, trendColor } from '../../lib/format.ts';
import type { SparkPoint } from '../../lib/api.ts';

interface TargetZone {
  min?: number;
  max?: number;
  label?: string;
}

interface GoalInfo {
  target: number;
  direction: 'above' | 'below';
}

interface Props {
  label: string;
  value: number | null;
  unit: string;
  trend: number | null;
  sparkline: SparkPoint[];
  color?: string;
  loading?: boolean;
  invertTrend?: boolean;
  target?: TargetZone;
  goal?: GoalInfo;
}

function targetStatus(value: number | null, target: TargetZone | undefined): 'in' | 'below' | 'above' | null {
  if (value == null || !target) return null;
  if (target.min != null && value < target.min) return 'below';
  if (target.max != null && value > target.max) return 'above';
  return 'in';
}

const statusStyles = {
  in: 'text-chart-emerald',
  below: 'text-chart-amber',
  above: 'text-chart-amber',
} as const;

export default function MetricCard({ label, value, unit, trend, sparkline, color = '#3B82F6', loading, invertTrend, target, goal }: Props) {
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
  const arrowColor = trendColor(trend, invertTrend);
  const status = targetStatus(value, target);

  // Goal progress
  let goalPct: number | null = null;
  let goalHit = false;
  if (goal && value != null) {
    if (goal.direction === 'above') {
      goalPct = Math.min(100, Math.round((value / goal.target) * 100));
      goalHit = value >= goal.target;
    } else {
      // For "below" goals: 100% when at or below target, scales down as value exceeds
      goalPct = value <= goal.target ? 100 : Math.max(0, Math.round((1 - (value - goal.target) / goal.target) * 100));
      goalHit = value <= goal.target;
    }
  }

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
      {target && status && (
        <p className={`text-xs mt-1 ${statusStyles[status]}`}>
          {status === 'in'
            ? `In range${target.label ? ` (${target.label})` : ''}`
            : status === 'below'
              ? `Below target${target.min != null ? ` (${target.min}${unit ? ' ' + unit : ''})` : ''}`
              : `Above target${target.max != null ? ` (${target.max}${unit ? ' ' + unit : ''})` : ''}`}
        </p>
      )}
      {goal && goalPct != null && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1">
            <span>Goal: {goal.target}{unit ? ` ${unit}` : ''}</span>
            <span className={goalHit ? 'text-chart-emerald' : ''}>{goalPct}%</span>
          </div>
          <div className="h-1.5 bg-bg-elevated rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${goalPct}%`,
                backgroundColor: goalHit ? '#10B981' : color,
              }}
            />
          </div>
        </div>
      )}
      <div className="mt-3 h-12">
        <SparkLine data={sparkline} color={color} />
      </div>
    </div>
  );
}
