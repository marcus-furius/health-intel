import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import BarChart from '../components/charts/BarChart.tsx';
import { useGoldenPhase } from '../hooks/queries.ts';
import { fmtNumber, fmtDateLong } from '../lib/format.ts';
import { chartColors, colors } from '../lib/colors.ts';

const STATUS_COLOR: Record<string, string> = {
  on_track: 'text-chart-sage',
  below: 'text-chart-terracotta',
  above: 'text-chart-terracotta',
  unknown: 'text-text-muted',
};

const STATUS_LABEL: Record<string, string> = {
  on_track: 'On Track',
  below: 'Below Target',
  above: 'Above Target',
  unknown: '—',
};

export default function GoldenPhase() {
  const { data: gp, isLoading } = useGoldenPhase();

  const recs = gp?.recommendations || [];
  const bodyChange = gp?.body_comp_change || {};
  const trajectory = gp?.scan_trajectory || [];
  const golden = gp?.golden_averages || {};
  const current = gp?.current_averages || {};
  const trainingProfile = gp?.training_profile || {};
  const compPeriods = gp?.comparison_periods || [];
  const muscleGroups = (trainingProfile.muscle_groups as { group: string; volume: number; pct: number }[]) || [];
  const workoutSplit = (trainingProfile.workout_split as { name: string; count: number }[]) || [];

  // Derive macro split for the recommendation donut-style display
  const macroSplit = golden.protein_pct || golden.carbs_pct || golden.fat_pct
    ? [
        { name: 'Protein', value: golden.protein_pct || 0, color: chartColors.recovery },
        { name: 'Carbs', value: golden.carbs_pct || 0, color: chartColors.nutrition },
        { name: 'Fat', value: golden.fat_pct || 0, color: chartColors.warning },
      ]
    : [];

  const hasData = gp && gp.period_start;

  return (
    <div>
      <Header title="Golden Phase" />

      {!hasData && !isLoading && (
        <p className="text-text-muted text-sm">
          Not enough body composition data to identify a golden phase. At least 4 scans spanning 6+ weeks are required.
        </p>
      )}

      {hasData && (
        <>
          {/* Period banner */}
          <div className="mb-8 p-5 rounded-2xl border border-accent-gold/30 bg-accent-gold/5">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="text-lg font-serif text-accent-gold">Peak Recomposition Period</h2>
              <span className="text-sm text-text-secondary">
                {fmtDateLong(gp!.period_start)} — {fmtDateLong(gp!.period_end)} ({gp!.duration_weeks} weeks)
              </span>
            </div>
            <p className="text-sm text-text-muted mt-1">
              The period with the best combined muscle gain and fat loss in your history. Use these metrics as targets.
            </p>
          </div>

          {/* Body comp change KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5 lg:gap-7 mb-10 animate-stagger">
            {bodyChange.muscle_mass_kg && (
              <MetricCard
                label="Muscle Gained"
                value={bodyChange.muscle_mass_kg.delta}
                unit="kg"
                trend={null}
                sparkline={[]}
                color={chartColors.recovery}
                loading={isLoading}
              />
            )}
            {bodyChange.body_fat_pct && (
              <MetricCard
                label="Body Fat Change"
                value={bodyChange.body_fat_pct.delta}
                unit="%"
                trend={null}
                sparkline={[]}
                color={chartColors.warning}
                loading={isLoading}
                invertTrend
              />
            )}
            {bodyChange.weight_kg && (
              <MetricCard
                label="Weight Change"
                value={bodyChange.weight_kg.delta}
                unit="kg"
                trend={null}
                sparkline={[]}
                color="#A69F95"
                loading={isLoading}
              />
            )}
            {bodyChange.fat_mass_kg && (
              <MetricCard
                label="Fat Mass Change"
                value={bodyChange.fat_mass_kg.delta}
                unit="kg"
                trend={null}
                sparkline={[]}
                color={chartColors.stress}
                loading={isLoading}
                invertTrend
              />
            )}
            {bodyChange.bmr && (
              <MetricCard
                label="BMR Change"
                value={bodyChange.bmr.delta}
                unit="kcal"
                trend={null}
                sparkline={[]}
                color={chartColors.nutrition}
                loading={isLoading}
              />
            )}
          </div>

          {/* Recommended Targets */}
          <ChartCard title="Recommended Targets" subtitle="Based on golden phase averages vs your current 30-day metrics" className="mb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                    <th className="text-right py-2 px-4 text-text-muted font-medium">Golden Phase</th>
                    <th className="text-right py-2 px-4 text-text-muted font-medium">Current (30d)</th>
                    <th className="text-right py-2 px-4 text-text-muted font-medium">Gap</th>
                    <th className="text-right py-2 pl-4 text-text-muted font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recs.map(r => {
                    const gap = r.golden_value != null && r.current_value != null
                      ? r.current_value - r.golden_value
                      : null;
                    return (
                      <tr key={r.metric} className="border-b border-border-subtle/50">
                        <td className="py-2.5 pr-4 text-text-primary font-medium">{r.metric}</td>
                        <td className="text-right py-2.5 px-4 text-accent-gold font-semibold">
                          {r.golden_value != null ? `${fmtNumber(r.golden_value, r.unit === 'g/kg' ? 1 : 0)} ${r.unit}` : '—'}
                        </td>
                        <td className="text-right py-2.5 px-4 text-text-primary">
                          {r.current_value != null ? `${fmtNumber(r.current_value, r.unit === 'g/kg' ? 1 : 0)} ${r.unit}` : '—'}
                        </td>
                        <td className={`text-right py-2.5 px-4 font-medium ${gap != null && gap >= 0 ? 'text-chart-sage' : 'text-chart-terracotta'}`}>
                          {gap != null ? `${gap >= 0 ? '+' : ''}${fmtNumber(gap, r.unit === 'g/kg' ? 1 : 0)}` : '—'}
                        </td>
                        <td className={`text-right py-2.5 pl-4 text-xs font-medium ${STATUS_COLOR[r.status] || ''}`}>
                          {STATUS_LABEL[r.status] || r.status}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </ChartCard>

          {/* Nutrition blueprint + Macro split */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
            <ChartCard title="Nutrition Blueprint" subtitle="Golden phase daily averages">
              <div className="space-y-4 py-2">
                {[
                  { label: 'Total Calories', value: golden.calories, unit: 'kcal', color: chartColors.nutrition },
                  { label: 'Protein', value: golden.protein_g, unit: 'g', color: chartColors.recovery, sub: golden.protein_pct ? `${golden.protein_pct}%` : undefined },
                  { label: 'Carbohydrates', value: golden.carbs_g, unit: 'g', color: colors.teal, sub: golden.carbs_pct ? `${golden.carbs_pct}%` : undefined },
                  { label: 'Fat', value: golden.fat_g, unit: 'g', color: chartColors.warning, sub: golden.fat_pct ? `${golden.fat_pct}%` : undefined },
                  { label: 'Protein/kg', value: golden.protein_per_kg, unit: 'g/kg', color: chartColors.recovery },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-sm text-text-secondary">{item.label}</span>
                    </div>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-lg font-serif text-text-primary">
                        {item.value != null ? fmtNumber(item.value, item.unit === 'g/kg' ? 1 : 0) : '—'}
                      </span>
                      <span className="text-xs text-text-muted">{item.unit}</span>
                      {item.sub && <span className="text-xs text-text-muted ml-1">({item.sub})</span>}
                    </div>
                  </div>
                ))}
              </div>
            </ChartCard>

            {macroSplit.length > 0 && (
              <ChartCard title="Macro Split" subtitle="Percentage of calories from each macro">
                <div className="flex items-center justify-center py-6">
                  <div className="flex gap-8">
                    {macroSplit.map(m => (
                      <div key={m.name} className="text-center">
                        <div
                          className="w-20 h-20 rounded-full flex items-center justify-center border-4 mx-auto mb-2"
                          style={{ borderColor: m.color }}
                        >
                          <span className="text-xl font-serif text-text-primary">{m.value}%</span>
                        </div>
                        <span className="text-xs text-text-muted">{m.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </ChartCard>
            )}
          </div>

          {/* Body comp trajectory + Training profile */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
            {trajectory.length > 0 && (
              <ChartCard title="Body Composition Trajectory" subtitle="During golden phase">
                <TrendChart
                  data={trajectory}
                  series={[
                    { dataKey: 'muscle_mass_kg', color: chartColors.recovery, name: 'Muscle (kg)', type: 'line' },
                    { dataKey: 'body_fat_pct', color: chartColors.warning, name: 'Body Fat %', type: 'line', yAxisId: 'right' },
                  ]}
                />
              </ChartCard>
            )}

            <ChartCard title="Training Blueprint" subtitle="Golden phase training profile">
              <div className="space-y-4 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Sessions/Week</span>
                  <span className="text-lg font-serif text-text-primary">
                    {golden.training_sessions_per_week != null ? fmtNumber(golden.training_sessions_per_week, 1) : '—'}
                  </span>
                </div>
                {trainingProfile.total_sessions != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">Total Sessions</span>
                    <span className="text-lg font-serif text-text-primary">{trainingProfile.total_sessions as number}</span>
                  </div>
                )}
                {trainingProfile.total_volume != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">Total Volume</span>
                    <span className="text-lg font-serif text-text-primary">
                      {fmtNumber(trainingProfile.total_volume as number, 0)} kg
                    </span>
                  </div>
                )}
                {workoutSplit.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border-subtle">
                    <p className="text-xs text-text-muted mb-2 uppercase tracking-wider">Workout Split</p>
                    {workoutSplit.map(w => (
                      <div key={w.name} className="flex items-center justify-between py-1">
                        <span className="text-sm text-text-secondary">{w.name}</span>
                        <span className="text-sm text-text-primary font-medium">{w.count}x</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </ChartCard>
          </div>

          {/* Muscle group distribution */}
          {muscleGroups.length > 0 && (
            <ChartCard title="Muscle Group Volume Distribution" subtitle="Golden phase training focus" className="mb-6">
              <BarChart
                data={muscleGroups.map(mg => ({ name: mg.group, volume: mg.volume }))}
                dataKey="volume"
                xKey="name"
                color={chartColors.training}
                horizontal
              />
            </ChartCard>
          )}

          {/* Recovery & Lifestyle targets */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
            <ChartCard title="Recovery & Lifestyle Targets">
              <div className="space-y-4 py-2">
                {[
                  { label: 'Sleep Score', golden: golden.sleep_score, current: current.sleep_score, color: chartColors.sleep },
                  { label: 'Readiness Score', golden: golden.readiness_score, current: current.readiness_score, color: chartColors.recovery },
                  { label: 'HRV Balance', golden: golden.hrv_balance, current: current.hrv_balance, color: chartColors.spo2 },
                  { label: 'Daily Steps', golden: golden.daily_steps, current: current.daily_steps, color: colors.violet },
                ].map(item => {
                  const pct = item.golden && item.current ? Math.min(100, Math.round((item.current / item.golden) * 100)) : 0;
                  return (
                    <div key={item.label}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-text-secondary">{item.label}</span>
                        <div className="flex items-baseline gap-2">
                          <span className="text-sm text-text-primary font-medium">
                            {item.current != null ? fmtNumber(item.current, item.label === 'Daily Steps' ? 0 : 0) : '—'}
                          </span>
                          <span className="text-xs text-text-muted">
                            / {item.golden != null ? fmtNumber(item.golden, item.label === 'Daily Steps' ? 0 : 0) : '—'}
                          </span>
                        </div>
                      </div>
                      <div className="h-2 rounded-full bg-bg-elevated overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: pct >= 95 ? chartColors.recovery : pct >= 80 ? item.color : chartColors.warning,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </ChartCard>

            {/* Period comparison */}
            {compPeriods.length > 0 && (
              <ChartCard title="Quarterly Comparison" subtitle="Body recomposition results by period">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border-subtle">
                        <th className="text-left py-2 pr-3 text-text-muted font-medium">Period</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium">Muscle</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium">BF%</th>
                        <th className="text-right py-2 px-2 text-text-muted font-medium">Cal/d</th>
                        <th className="text-right py-2 pl-2 text-text-muted font-medium">Train/wk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compPeriods.map((p, i) => (
                        <tr
                          key={i}
                          className={`border-b border-border-subtle/50 ${p.is_golden ? 'bg-accent-gold/5' : ''}`}
                        >
                          <td className={`py-2 pr-3 ${p.is_golden as boolean ? 'text-accent-gold font-medium' : 'text-text-primary'}`}>
                            {p.label as string}
                            {(p.is_golden as boolean) && <span className="text-xs ml-1">★</span>}
                          </td>
                          <td className={`text-right py-2 px-2 font-medium ${
                            (p.muscle_delta_kg as number) > 0 ? 'text-chart-sage' : (p.muscle_delta_kg as number) < 0 ? 'text-chart-rose' : 'text-text-muted'
                          }`}>
                            {p.muscle_delta_kg != null ? `${(p.muscle_delta_kg as number) > 0 ? '+' : ''}${fmtNumber(p.muscle_delta_kg as number, 1)} kg` : '—'}
                          </td>
                          <td className={`text-right py-2 px-2 font-medium ${
                            (p.fat_pct_delta as number) < 0 ? 'text-chart-sage' : (p.fat_pct_delta as number) > 0 ? 'text-chart-rose' : 'text-text-muted'
                          }`}>
                            {p.fat_pct_delta != null ? `${(p.fat_pct_delta as number) > 0 ? '+' : ''}${fmtNumber(p.fat_pct_delta as number, 1)}%` : '—'}
                          </td>
                          <td className="text-right py-2 px-2 text-text-secondary">
                            {p.avg_calories != null ? fmtNumber(p.avg_calories as number, 0) : '—'}
                          </td>
                          <td className="text-right py-2 pl-2 text-text-secondary">
                            {p.training_per_week != null ? fmtNumber(p.training_per_week as number, 1) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}
          </div>
        </>
      )}
    </div>
  );
}
