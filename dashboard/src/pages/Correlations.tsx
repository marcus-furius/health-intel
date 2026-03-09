import Header from '../components/layout/Header.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import ScatterPlot from '../components/charts/ScatterPlot.tsx';
import Skeleton from '../components/ui/Skeleton.tsx';
import Badge from '../components/ui/Badge.tsx';
import { useCorrelations } from '../hooks/queries.ts';

function guessKeys(points: Record<string, unknown>[]): [string, string] {
  if (!points.length) return ['', ''];
  const keys = Object.keys(points[0]).filter(k => k !== 'day');
  return [keys[0] || '', keys[1] || ''];
}

function ciLabel(ci_low?: number | null, ci_high?: number | null): string | null {
  if (ci_low == null || ci_high == null) return null;
  return `95% CI: [${ci_low.toFixed(2)}, ${ci_high.toFixed(2)}]`;
}

function ciSpansZero(ci_low?: number | null, ci_high?: number | null): boolean {
  if (ci_low == null || ci_high == null) return false;
  return ci_low < 0 && ci_high > 0;
}

export default function Correlations() {
  const { data: corrRes, isLoading } = useCorrelations();
  const correlations = corrRes?.correlations || [];

  return (
    <div>
      <Header title="Correlations" />

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-bg-card border border-border-subtle rounded-2xl p-7">
              <Skeleton className="h-6 w-48 mb-4" />
              <Skeleton className="h-52 w-full" />
            </div>
          ))}
        </div>
      ) : correlations.length === 0 ? (
        <p className="text-text-muted">Not enough data to compute correlations (minimum 14 data points per pair).</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7">
          {correlations.map(c => {
            const [xKey, yKey] = guessKeys(c.points as Record<string, unknown>[]);
            const ci = ciLabel(c.ci_low, c.ci_high);
            const unstable = ciSpansZero(c.ci_low, c.ci_high);
            const subtitle = [
              c.lag_days ? `Best lag: ${c.lag_days}d` : 'Same-day',
              c.n_samples ? `n=${c.n_samples}` : null,
            ].filter(Boolean).join(' · ');
            return (
              <ChartCard key={c.key} title={`${c.x_label} vs ${c.y_label}`} subtitle={subtitle}>
                <ScatterPlot
                  data={c.points as Record<string, unknown>[]}
                  xKey={xKey}
                  yKey={yKey}
                  xLabel={c.x_label}
                  yLabel={c.y_label}
                  rValue={c.r_value}
                  strength={c.strength}
                />
                {ci && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-text-muted">{ci}</span>
                    {unstable && <Badge label="Spans zero" variant="medium" />}
                  </div>
                )}
              </ChartCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
