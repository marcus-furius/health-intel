import Header from '../components/layout/Header.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import ScatterPlot from '../components/charts/ScatterPlot.tsx';
import Skeleton from '../components/ui/Skeleton.tsx';
import { useCorrelations } from '../hooks/queries.ts';

function guessKeys(points: Record<string, unknown>[]): [string, string] {
  if (!points.length) return ['', ''];
  const keys = Object.keys(points[0]).filter(k => k !== 'day');
  return [keys[0] || '', keys[1] || ''];
}

export default function Correlations() {
  const { data: corrRes, isLoading } = useCorrelations();
  const correlations = corrRes?.correlations || [];

  return (
    <div>
      <Header title="Correlations" />

      {isLoading ? (
        <div className="grid grid-cols-2 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-bg-card border border-border-subtle rounded-xl p-6">
              <Skeleton className="h-6 w-48 mb-4" />
              <Skeleton className="h-52 w-full" />
            </div>
          ))}
        </div>
      ) : correlations.length === 0 ? (
        <p className="text-text-muted">Not enough data to compute correlations (minimum 14 data points per pair).</p>
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {correlations.map(c => {
            const [xKey, yKey] = guessKeys(c.points as Record<string, unknown>[]);
            return (
              <ChartCard key={c.key} title={`${c.x_label} vs ${c.y_label}`}>
                <ScatterPlot
                  data={c.points as Record<string, unknown>[]}
                  xKey={xKey}
                  yKey={yKey}
                  xLabel={c.x_label}
                  yLabel={c.y_label}
                  rValue={c.r_value}
                  strength={c.strength}
                />
              </ChartCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
