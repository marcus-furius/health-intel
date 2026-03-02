import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import AlertCard from '../components/ui/AlertCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import ScatterPlot from '../components/charts/ScatterPlot.tsx';
import { useOverview, useSleep, useReadiness, useStress, useCorrelations } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

function weeklyAggregate(data: Record<string, unknown>[], valueKey: string): Record<string, unknown>[] {
  const weeks: Record<string, { sum: number; count: number }> = {};
  for (const row of data) {
    const day = row.day as string;
    if (!day) continue;
    const d = new Date(day);
    // ISO week start (Monday)
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const key = monday.toISOString().split('T')[0];
    const val = row[valueKey] as number;
    if (val == null || isNaN(val)) continue;
    if (!weeks[key]) weeks[key] = { sum: 0, count: 0 };
    weeks[key].sum += val;
    weeks[key].count++;
  }
  return Object.entries(weeks)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, { sum, count }]) => ({ day, [valueKey]: Math.round(sum / count) }));
}

export default function Overview() {
  const { params } = useDateRange();
  const { data: overview, isLoading } = useOverview();
  const { data: sleepRes } = useSleep(params);
  const { data: readinessRes } = useReadiness(params);
  const { data: stressRes } = useStress(params);
  const { data: corrRes } = useCorrelations();

  const metricColors = [
    chartColors.sleep,
    chartColors.recovery,
    '#3B82F6',
    chartColors.nutrition,
    chartColors.training,
    '#A1A1AA',
  ];

  // Build weekly overlay chart data
  const sleepWeekly = sleepRes?.data ? weeklyAggregate(sleepRes.data, 'score') : [];
  const readinessWeekly = readinessRes?.data ? weeklyAggregate(readinessRes.data, 'score') : [];
  const overlayData = sleepWeekly.map(sw => {
    const rw = readinessWeekly.find(r => r.day === sw.day);
    return {
      day: sw.day as string,
      sleep_score: sw.score as number,
      readiness_score: rw?.score as number | undefined,
    };
  });

  // Stress weekly
  const stressWeekly = stressRes?.data
    ? (() => {
        const weeks: Record<string, { stress: number; recovery: number; count: number }> = {};
        for (const row of stressRes.data) {
          const day = row.day as string;
          if (!day) continue;
          const d = new Date(day);
          const monday = new Date(d);
          monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
          const key = monday.toISOString().split('T')[0];
          if (!weeks[key]) weeks[key] = { stress: 0, recovery: 0, count: 0 };
          weeks[key].stress += (row.stress_high as number) || 0;
          weeks[key].recovery += (row.recovery_high as number) || 0;
          weeks[key].count++;
        }
        return Object.entries(weeks)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([day, { stress, recovery, count }]) => ({
            day,
            stress: Math.round(stress / count),
            recovery: Math.round(recovery / count),
          }));
      })()
    : [];

  const topCorrelations = corrRes?.correlations?.slice(0, 3) || [];

  return (
    <div>
      <Header title="Overview" />

      {/* Metric cards */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <MetricCard key={i} label="" value={null} unit="" trend={null} sparkline={[]} loading />
            ))
          : overview?.metrics.map((m, i) => (
              <MetricCard
                key={m.label}
                label={m.label}
                value={m.value}
                unit={m.unit}
                trend={m.trend}
                sparkline={m.sparkline}
                color={metricColors[i] || '#3B82F6'}
              />
            ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <ChartCard title="Sleep & Readiness" subtitle="Weekly averages">
          <TrendChart
            data={overlayData}
            series={[
              { dataKey: 'sleep_score', color: chartColors.sleep, name: 'Sleep Score' },
              { dataKey: 'readiness_score', color: chartColors.recovery, name: 'Readiness', type: 'line' },
            ]}
          />
        </ChartCard>
        <ChartCard title="Stress vs Recovery" subtitle="Weekly avg minutes">
          <StackedBar
            data={stressWeekly}
            series={[
              { dataKey: 'recovery', color: chartColors.recovery, name: 'Recovery (min)' },
              { dataKey: 'stress', color: chartColors.stress, name: 'Stress (min)' },
            ]}
          />
        </ChartCard>
      </div>

      {/* Alerts + Correlations */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-medium mb-4">Top Alerts</h2>
          <div className="space-y-3">
            {overview?.alerts.slice(0, 3).map((a, i) => (
              <AlertCard key={i} alert={a} />
            ))}
            {overview && overview.alerts.length === 0 && (
              <p className="text-sm text-text-muted">No alerts — all metrics within healthy ranges.</p>
            )}
          </div>
        </div>
        <div>
          <h2 className="text-lg font-medium mb-4">Strongest Correlations</h2>
          <div className="space-y-4">
            {topCorrelations.map(c => {
              const xKey = Object.keys(c.points[0] || {}).find(k => k !== 'day') || '';
              const yKey = Object.keys(c.points[0] || {}).filter(k => k !== 'day' && k !== xKey)[0] || '';
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
                    height={160}
                  />
                </ChartCard>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
