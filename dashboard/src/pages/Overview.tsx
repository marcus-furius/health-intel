import { useState } from 'react';
import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import AlertCard from '../components/ui/AlertCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import ScatterPlot from '../components/charts/ScatterPlot.tsx';
import CalendarHeatmap from '../components/charts/CalendarHeatmap.tsx';
import Badge from '../components/ui/Badge.tsx';
import { useOverview, useSleep, useReadiness, useActivity, useStress, useNutrition, useCorrelations, useRecords, useCompare, useStreaks, useTrainingRecommendation, useInterventionImpact } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';
import { fmtNumber, fmtDate } from '../lib/format.ts';
import { useGoals } from '../hooks/useGoals.ts';
import { useInterventions } from '../hooks/useInterventions.ts';
import type { Intervention } from '../hooks/useInterventions.ts';

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
  const { getGoal } = useGoals();
  const { data: sleepRes } = useSleep(params);
  const { data: readinessRes } = useReadiness(params);
  const { data: stressRes } = useStress(params);
  const { data: activityRes } = useActivity(params);
  const { data: nutritionRes } = useNutrition(params);
  const { data: corrRes } = useCorrelations();
  const { data: recordsRes } = useRecords();
  const { data: streaksRes } = useStreaks();
  const { data: trainingRec } = useTrainingRecommendation();
  const { interventions, addIntervention, removeIntervention } = useInterventions();
  const [selectedIntervention, setSelectedIntervention] = useState<Intervention | null>(null);
  const { data: impactRes } = useInterventionImpact(
    selectedIntervention?.date || '',
    14,
    !!selectedIntervention,
  );
  const [newIntLabel, setNewIntLabel] = useState('');
  const [newIntDate, setNewIntDate] = useState('');
  const [newIntCat, setNewIntCat] = useState<Intervention['category']>('lifestyle');

  // Period comparison — default: last 30 days vs previous 30 days
  const [showCompare, setShowCompare] = useState(false);
  const today = new Date();
  const thirtyAgo = new Date(today);
  thirtyAgo.setDate(today.getDate() - 30);
  const sixtyAgo = new Date(today);
  sixtyAgo.setDate(today.getDate() - 60);
  const fmt = (d: Date) => d.toISOString().split('T')[0];
  const [compA, setCompA] = useState({ start: fmt(sixtyAgo), end: fmt(thirtyAgo) });
  const [compB, setCompB] = useState({ start: fmt(thirtyAgo), end: fmt(today) });
  const { data: compareRes } = useCompare(compA.start, compA.end, compB.start, compB.end, showCompare);

  // Heatmap metric options
  const heatmapMetrics = [
    { key: 'score', label: 'Sleep Score', data: sleepRes?.data || [], color: chartColors.sleep },
    { key: 'score', label: 'Readiness', data: readinessRes?.data || [], color: chartColors.recovery },
    { key: 'steps', label: 'Steps', data: activityRes?.data || [], color: '#C9A96E' },
    { key: 'calories', label: 'Calories', data: nutritionRes?.data || [], color: chartColors.nutrition },
  ];
  const [heatmapIdx, setHeatmapIdx] = useState(0);
  const activeHeatmap = heatmapMetrics[heatmapIdx];

  const metricColors = [
    chartColors.sleep,       // Sleep Score
    chartColors.recovery,    // Readiness
    '#C9A96E',               // Daily Steps
    chartColors.warning,     // Sedentary
    chartColors.nutrition,   // Avg Calories
    chartColors.stress,      // Resting HR
    chartColors.nutrition,   // Logging %
    chartColors.training,    // Volume/Week
    '#A69F95',               // Weight
    chartColors.warning,     // Cal Balance
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
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-5 lg:gap-7 mb-10 animate-stagger">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <MetricCard key={i} label="" value={null} unit="" trend={null} sparkline={[]} loading />
            ))
          : overview?.metrics.map((m, i) => {
              const g = getGoal(m.label);
              return (
                <MetricCard
                  key={m.label}
                  label={m.label}
                  value={m.value}
                  unit={m.unit}
                  trend={m.trend}
                  sparkline={m.sparkline}
                  color={metricColors[i] || '#C9A96E'}
                  invertTrend={m.invert_trend}
                  target={m.target ?? undefined}
                  goal={g ? { target: g.target, direction: g.direction } : undefined}
                />
              );
            })}
      </div>

      {/* Training Recommendation + Streaks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-8">
        {/* Training Recommendation */}
        {trainingRec && trainingRec.score != null && (
          <ChartCard title="Today's Training Readiness" subtitle={trainingRec.detail}>
            <div className="flex items-center gap-4">
              <div className="relative w-20 h-20">
                <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
                  <circle cx="18" cy="18" r="15.5" fill="none" stroke="currentColor" className="text-border-subtle" strokeWidth="3" />
                  <circle
                    cx="18" cy="18" r="15.5" fill="none"
                    stroke={trainingRec.intensity === 'hard' ? chartColors.recovery : trainingRec.intensity === 'moderate' ? '#C9A96E' : trainingRec.intensity === 'light' ? chartColors.warning : chartColors.stress}
                    strokeWidth="3"
                    strokeDasharray={`${trainingRec.score * 0.9738} 97.38`}
                    strokeLinecap="round"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-lg font-bold">{trainingRec.score}</span>
              </div>
              <div className="flex-1">
                <Badge
                  label={trainingRec.intensity.charAt(0).toUpperCase() + trainingRec.intensity.slice(1)}
                  variant={trainingRec.intensity === 'hard' ? 'high' : trainingRec.intensity === 'moderate' ? 'medium' : 'low'}
                />
                {trainingRec.components && (
                  <div className="grid grid-cols-3 gap-2 mt-3 text-xs text-text-muted">
                    <div>Readiness <span className="block text-text-primary font-medium">{trainingRec.components.readiness}</span></div>
                    <div>HRV <span className="block text-text-primary font-medium">{trainingRec.components.hrv_balance}</span></div>
                    <div>Load Factor <span className="block text-text-primary font-medium">{trainingRec.components.load_factor}</span></div>
                  </div>
                )}
              </div>
            </div>
          </ChartCard>
        )}

        {/* Streaks */}
        {(streaksRes?.streaks || []).length > 0 && (
          <ChartCard title="Streaks" subtitle="Consecutive days hitting targets">
            <div className="space-y-3">
              {streaksRes!.streaks.map(s => (
                <div key={s.metric} className="flex items-center justify-between">
                  <div>
                    <span className="text-sm text-text-primary font-medium">{s.metric}</span>
                    <span className="text-xs text-text-muted ml-2">{s.target}</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className={`font-semibold ${s.current > 0 ? 'text-chart-sage' : 'text-text-muted'}`}>
                      {s.current} {s.unit}
                    </span>
                    <span className="text-text-muted text-xs">best: {s.best}</span>
                  </div>
                </div>
              ))}
            </div>
          </ChartCard>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-8">
        <ChartCard title="Sleep & Readiness" subtitle="Weekly averages" exportData={overlayData}>
          <TrendChart
            data={overlayData}
            series={[
              { dataKey: 'sleep_score', color: chartColors.sleep, name: 'Sleep Score' },
              { dataKey: 'readiness_score', color: chartColors.recovery, name: 'Readiness', type: 'line' },
            ]}
          />
        </ChartCard>
        <ChartCard title="Stress vs Recovery" subtitle="Weekly avg minutes" exportData={stressWeekly}>
          <StackedBar
            data={stressWeekly}
            series={[
              { dataKey: 'recovery', color: chartColors.recovery, name: 'Recovery (min)' },
              { dataKey: 'stress', color: chartColors.stress, name: 'Stress (min)' },
            ]}
          />
        </ChartCard>
      </div>

      {/* Period comparison */}
      <div className="mb-8">
        <button
          onClick={() => setShowCompare(!showCompare)}
          className="text-sm text-text-secondary hover:text-text-primary transition-colors mb-4"
        >
          {showCompare ? 'Hide' : 'Show'} Period Comparison
        </button>
        {showCompare && (
          <ChartCard title="Period Comparison" subtitle="Compare two date ranges">
            <div className="flex flex-wrap gap-4 mb-4">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-text-muted">Period A:</span>
                <input type="date" value={compA.start} onChange={e => setCompA(p => ({ ...p, start: e.target.value }))} className="bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-text-primary text-sm" />
                <span className="text-text-muted">to</span>
                <input type="date" value={compA.end} onChange={e => setCompA(p => ({ ...p, end: e.target.value }))} className="bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-text-primary text-sm" />
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-text-muted">Period B:</span>
                <input type="date" value={compB.start} onChange={e => setCompB(p => ({ ...p, start: e.target.value }))} className="bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-text-primary text-sm" />
                <span className="text-text-muted">to</span>
                <input type="date" value={compB.end} onChange={e => setCompB(p => ({ ...p, end: e.target.value }))} className="bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-text-primary text-sm" />
              </div>
            </div>
            {compareRes?.comparisons && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">Period A</th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">Period B</th>
                      <th className="text-right py-2 pl-4 text-text-muted font-medium">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareRes.comparisons.map(c => (
                      <tr key={c.label} className="border-b border-border-subtle/50">
                        <td className="py-2 pr-4 text-text-primary">{c.label}</td>
                        <td className="text-right py-2 px-4 text-text-secondary">
                          {c.period_a != null ? fmtNumber(c.period_a, 1) : '—'}
                        </td>
                        <td className="text-right py-2 px-4 text-text-primary font-medium">
                          {c.period_b != null ? fmtNumber(c.period_b, 1) : '—'}
                        </td>
                        <td className={`text-right py-2 pl-4 font-medium ${
                          c.improved == null ? 'text-text-muted' : c.improved ? 'text-chart-sage' : 'text-chart-rose'
                        }`}>
                          {c.delta != null ? `${c.delta > 0 ? '+' : ''}${fmtNumber(c.delta, 1)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartCard>
        )}
      </div>

      {/* Calendar heatmap */}
      <div className="mb-8">
        <ChartCard title="Daily Activity" subtitle={activeHeatmap.label}>
          <div className="flex gap-2 mb-4">
            {heatmapMetrics.map((m, i) => (
              <button
                key={i}
                onClick={() => setHeatmapIdx(i)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  i === heatmapIdx
                    ? 'bg-accent-gold/10 text-accent-gold font-medium'
                    : 'text-text-muted hover:text-text-secondary'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <CalendarHeatmap
            data={activeHeatmap.data}
            dataKey={activeHeatmap.key}
            color={activeHeatmap.color}
          />
        </ChartCard>
      </div>

      {/* Personal records */}
      {(recordsRes?.records || []).length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-serif mb-4">Personal Records</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {recordsRes!.records.map((r, i) => (
              <div key={i} className="bg-bg-card border border-border-subtle rounded-2xl p-4">
                <p className="text-xs text-text-muted font-medium truncate">{r.label}</p>
                <p className="text-2xl font-serif tracking-tight mt-1">
                  {fmtNumber(r.value, r.value % 1 !== 0 ? 1 : 0)}
                  {r.unit && <span className="text-sm text-text-muted ml-1">{r.unit}</span>}
                </p>
                {r.date && <p className="text-xs text-text-muted mt-1">{fmtDate(r.date)}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Intervention Tracking */}
      <div className="mb-8">
        <h2 className="text-lg font-serif mb-4">Intervention Tracking</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7">
          <ChartCard title="Log Intervention" subtitle="Track when you change something">
            <div className="space-y-3">
              <input
                type="text"
                placeholder='e.g. "Started sleeping earlier", "Added creatine"'
                value={newIntLabel}
                onChange={e => setNewIntLabel(e.target.value)}
                className="w-full bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted"
              />
              <div className="flex gap-2">
                <input
                  type="date"
                  value={newIntDate}
                  onChange={e => setNewIntDate(e.target.value)}
                  className="bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary flex-1"
                />
                <select
                  value={newIntCat}
                  onChange={e => setNewIntCat(e.target.value as Intervention['category'])}
                  className="bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary"
                >
                  <option value="sleep">Sleep</option>
                  <option value="nutrition">Nutrition</option>
                  <option value="training">Training</option>
                  <option value="supplement">Supplement</option>
                  <option value="lifestyle">Lifestyle</option>
                </select>
                <button
                  onClick={() => {
                    if (newIntLabel && newIntDate) {
                      addIntervention(newIntLabel, newIntDate, newIntCat);
                      setNewIntLabel('');
                      setNewIntDate('');
                    }
                  }}
                  disabled={!newIntLabel || !newIntDate}
                  className="px-4 py-2 bg-accent-gold text-white rounded-xl text-sm font-medium disabled:opacity-40 hover:opacity-90 transition-opacity"
                >
                  Add
                </button>
              </div>
              {interventions.length > 0 && (
                <div className="space-y-2 mt-4">
                  {interventions.sort((a, b) => b.date.localeCompare(a.date)).map(int => (
                    <div
                      key={int.id}
                      className={`flex items-center justify-between p-2 rounded-lg text-sm cursor-pointer transition-colors ${
                        selectedIntervention?.id === int.id ? 'bg-bg-elevated border border-border-default' : 'hover:bg-bg-elevated/50'
                      }`}
                      onClick={() => setSelectedIntervention(selectedIntervention?.id === int.id ? null : int)}
                    >
                      <div>
                        <span className="text-text-primary font-medium">{int.label}</span>
                        <span className="text-text-muted ml-2 text-xs">{fmtDate(int.date)}</span>
                        <Badge label={int.category} variant="low" />
                      </div>
                      <button
                        onClick={e => { e.stopPropagation(); removeIntervention(int.id); if (selectedIntervention?.id === int.id) setSelectedIntervention(null); }}
                        className="text-text-muted hover:text-chart-rose text-xs"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ChartCard>

          {/* Impact view */}
          <ChartCard
            title={selectedIntervention ? `Impact: ${selectedIntervention.label}` : 'Select an Intervention'}
            subtitle={selectedIntervention ? `14 days before vs after ${fmtDate(selectedIntervention.date)}` : 'Click an intervention to see before/after metrics'}
          >
            {impactRes?.metrics ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">Before</th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">After</th>
                      <th className="text-right py-2 pl-4 text-text-muted font-medium">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {impactRes.metrics.map(m => (
                      <tr key={m.label} className="border-b border-border-subtle/50">
                        <td className="py-2 pr-4 text-text-primary">{m.label}</td>
                        <td className="text-right py-2 px-4 text-text-secondary">
                          {m.before != null ? fmtNumber(m.before, 1) : '—'}
                        </td>
                        <td className="text-right py-2 px-4 text-text-primary font-medium">
                          {m.after != null ? fmtNumber(m.after, 1) : '—'}
                        </td>
                        <td className={`text-right py-2 pl-4 font-medium ${
                          m.improved == null ? 'text-text-muted' : m.improved ? 'text-chart-sage' : 'text-chart-rose'
                        }`}>
                          {m.delta != null ? `${m.delta > 0 ? '+' : ''}${fmtNumber(m.delta, 1)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-text-muted">No intervention selected.</p>
            )}
          </ChartCard>
        </div>
      </div>

      {/* Alerts + Correlations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7">
        <div>
          <h2 className="text-lg font-serif mb-4">Top Alerts</h2>
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
          <h2 className="text-lg font-serif mb-4">Strongest Correlations</h2>
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
