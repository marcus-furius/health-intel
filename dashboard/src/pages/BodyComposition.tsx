import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import { useBodyComposition, useWeight, useForecasts } from '../hooks/queries.ts';
import { fmtNumber, fmtDateLong } from '../lib/format.ts';
import { chartColors } from '../lib/colors.ts';

export default function BodyComposition() {
  const { data: bodyRes, isLoading } = useBodyComposition();
  const { data: weightRes } = useWeight();

  const { data: forecastsRes } = useForecasts();
  const scans = bodyRes?.data || [];
  const latest = scans.length ? scans[scans.length - 1] : null;
  const first = scans.length >= 2 ? scans[0] : null;
  const weightData = weightRes?.data || [];
  const forecasts = forecastsRes?.forecasts || [];

  // Segmental asymmetry detection
  const segmentalData = latest ? [
    {
      region: 'Left Arm',
      muscle: latest.left_arm_muscle_kg as number | null,
      fat: latest.left_arm_fat_kg as number | null,
    },
    {
      region: 'Right Arm',
      muscle: latest.right_arm_muscle_kg as number | null,
      fat: latest.right_arm_fat_kg as number | null,
    },
    {
      region: 'Left Leg',
      muscle: latest.left_leg_muscle_kg as number | null,
      fat: latest.left_leg_fat_kg as number | null,
    },
    {
      region: 'Right Leg',
      muscle: latest.right_leg_muscle_kg as number | null,
      fat: latest.right_leg_fat_kg as number | null,
    },
    {
      region: 'Trunk',
      muscle: latest.trunk_muscle_kg as number | null,
      fat: latest.trunk_fat_kg as number | null,
    },
  ] : [];

  const hasSegmental = segmentalData.some(s => s.muscle != null || s.fat != null);

  // Compute asymmetries
  const asymmetries: { label: string; diff: number; pct: number }[] = [];
  if (latest) {
    const pairs: [string, string, string][] = [
      ['Arm Muscle', 'left_arm_muscle_kg', 'right_arm_muscle_kg'],
      ['Arm Fat', 'left_arm_fat_kg', 'right_arm_fat_kg'],
      ['Leg Muscle', 'left_leg_muscle_kg', 'right_leg_muscle_kg'],
      ['Leg Fat', 'left_leg_fat_kg', 'right_leg_fat_kg'],
    ];
    for (const [label, leftKey, rightKey] of pairs) {
      const left = latest[leftKey] as number | null;
      const right = latest[rightKey] as number | null;
      if (left != null && right != null && (left + right) > 0) {
        const diff = Math.abs(left - right);
        const avg = (left + right) / 2;
        const pct = (diff / avg) * 100;
        if (pct > 5) {
          asymmetries.push({ label, diff: +diff.toFixed(2), pct: +pct.toFixed(1) });
        }
      }
    }
  }

  // Phase angle data
  const hasPhaseAngle = scans.some(s => s.phase_angle_left_arm != null);

  // Water distribution
  const hasWater = scans.some(s => s.intracellular_water_kg != null);

  return (
    <div>
      <Header title="Body Composition" />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 mb-8">
        <MetricCard label="Weight" value={latest?.weight_kg as number} unit="kg" trend={null} sparkline={[]} color="#A1A1AA" loading={isLoading} />
        <MetricCard label="Body Fat" value={latest?.body_fat_pct as number} unit="%" trend={null} sparkline={[]} color={chartColors.warning} loading={isLoading} invertTrend />
        <MetricCard label="Muscle Mass" value={latest?.muscle_mass_kg as number} unit="kg" trend={null} sparkline={[]} color={chartColors.recovery} loading={isLoading} />
        <MetricCard label="Visceral Fat" value={latest?.visceral_fat as number} unit="rating" trend={null} sparkline={[]} color={chartColors.stress} loading={isLoading} invertTrend />
        <MetricCard label="Metabolic Age" value={latest?.metabolic_age as number} unit="yrs" trend={null} sparkline={[]} color={chartColors.sleep} loading={isLoading} invertTrend />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Weight Trajectory" subtitle="Boditrax scans + MFP daily">
          <TrendChart
            data={weightData as Record<string, unknown>[]}
            series={[{ dataKey: 'weight_kg', color: '#A1A1AA', name: 'Weight (kg)', type: 'line' }]}
          />
        </ChartCard>
        <ChartCard title="Body Fat % Trend">
          <TrendChart
            data={scans as Record<string, unknown>[]}
            series={[{ dataKey: 'body_fat_pct', color: chartColors.warning, name: 'Body Fat %', type: 'line' }]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Muscle Mass Trend">
          <TrendChart
            data={scans as Record<string, unknown>[]}
            series={[{ dataKey: 'muscle_mass_kg', color: chartColors.recovery, name: 'Muscle Mass (kg)', type: 'line' }]}
          />
        </ChartCard>
        <ChartCard title="BMR Trend">
          <TrendChart
            data={scans as Record<string, unknown>[]}
            series={[{ dataKey: 'bmr', color: chartColors.nutrition, name: 'BMR (kcal)', type: 'line' }]}
          />
        </ChartCard>
      </div>

      {/* Phase angle & water distribution */}
      {(hasPhaseAngle || hasWater) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
          {hasPhaseAngle && (
            <ChartCard title="Phase Angle Trend" subtitle="Cellular health indicator">
              <TrendChart
                data={scans as Record<string, unknown>[]}
                series={[
                  { dataKey: 'phase_angle_left_arm', color: chartColors.recovery, name: 'Left Arm', type: 'line' },
                  { dataKey: 'phase_angle_right_arm', color: chartColors.training, name: 'Right Arm', type: 'line' },
                  { dataKey: 'phase_angle_left_leg', color: chartColors.sleep, name: 'Left Leg', type: 'line' },
                  { dataKey: 'phase_angle_right_leg', color: chartColors.nutrition, name: 'Right Leg', type: 'line' },
                ]}
              />
            </ChartCard>
          )}
          {hasWater && (
            <ChartCard title="Water Distribution" subtitle="Intracellular vs Extracellular">
              <TrendChart
                data={scans as Record<string, unknown>[]}
                series={[
                  { dataKey: 'intracellular_water_kg', color: chartColors.sleep, name: 'Intracellular (kg)', type: 'line' },
                  { dataKey: 'extracellular_water_kg', color: chartColors.spo2, name: 'Extracellular (kg)', type: 'line' },
                ]}
              />
            </ChartCard>
          )}
        </div>
      )}

      {/* Segmental breakdown */}
      {hasSegmental && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
          <ChartCard title="Segmental Breakdown" subtitle={latest ? fmtDateLong(latest.day as string) : ''}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">Region</th>
                    <th className="text-right py-2 px-4 text-text-muted font-medium">Muscle (kg)</th>
                    <th className="text-right py-2 pl-4 text-text-muted font-medium">Fat (kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {segmentalData.map(({ region, muscle, fat }) => (
                    <tr key={region} className="border-b border-border-subtle/50">
                      <td className="py-2 pr-4 text-text-primary">{region}</td>
                      <td className="text-right py-2 px-4 text-text-secondary">
                        {muscle != null ? fmtNumber(muscle, 2) : '—'}
                      </td>
                      <td className="text-right py-2 pl-4 text-text-secondary">
                        {fat != null ? fmtNumber(fat, 2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {asymmetries.length > 0 && (
              <div className="mt-4 space-y-1">
                {asymmetries.map(a => (
                  <p key={a.label} className="text-xs text-chart-amber">
                    ⚠ {a.label} asymmetry: {a.pct}% difference ({a.diff} kg)
                  </p>
                ))}
              </div>
            )}
          </ChartCard>

          {/* Comparison table */}
          {first && latest && (
            <ChartCard title="First vs Latest Scan">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">
                        {fmtDateLong(first.day as string)}
                      </th>
                      <th className="text-right py-2 px-4 text-text-muted font-medium">
                        {fmtDateLong(latest.day as string)}
                      </th>
                      <th className="text-right py-2 pl-4 text-text-muted font-medium">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: 'Weight', key: 'weight_kg', unit: 'kg', decimals: 1 },
                      { label: 'Body Fat', key: 'body_fat_pct', unit: '%', decimals: 1 },
                      { label: 'Muscle Mass', key: 'muscle_mass_kg', unit: 'kg', decimals: 1 },
                      { label: 'Fat Mass', key: 'fat_mass_kg', unit: 'kg', decimals: 1 },
                      { label: 'Visceral Fat', key: 'visceral_fat', unit: '', decimals: 0 },
                      { label: 'BMR', key: 'bmr', unit: 'kcal', decimals: 0 },
                      { label: 'BMI', key: 'bmi', unit: '', decimals: 1 },
                      { label: 'Metabolic Age', key: 'metabolic_age', unit: 'yrs', decimals: 0 },
                    ].map(({ label, key, unit, decimals }) => {
                      const firstVal = first[key] as number | null;
                      const latestVal = latest[key] as number | null;
                      const delta = firstVal != null && latestVal != null ? latestVal - firstVal : null;
                      return (
                        <tr key={key} className="border-b border-border-subtle/50">
                          <td className="py-2 pr-4 text-text-primary">{label}</td>
                          <td className="text-right py-2 px-4 text-text-secondary">
                            {firstVal != null ? `${fmtNumber(firstVal, decimals)} ${unit}` : '—'}
                          </td>
                          <td className="text-right py-2 px-4 text-text-primary font-medium">
                            {latestVal != null ? `${fmtNumber(latestVal, decimals)} ${unit}` : '—'}
                          </td>
                          <td className={`text-right py-2 pl-4 font-medium ${
                            delta == null ? 'text-text-muted' : delta > 0 ? 'text-chart-amber' : delta < 0 ? 'text-chart-emerald' : 'text-text-muted'
                          }`}>
                            {delta != null ? `${delta > 0 ? '+' : ''}${fmtNumber(delta, decimals)}` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </ChartCard>
          )}
        </div>
      )}

      {/* Fallback comparison table when no segmental data */}
      {!hasSegmental && first && latest && (
        <ChartCard title="First vs Latest Scan">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                  <th className="text-right py-2 px-4 text-text-muted font-medium">
                    {fmtDateLong(first.day as string)}
                  </th>
                  <th className="text-right py-2 px-4 text-text-muted font-medium">
                    {fmtDateLong(latest.day as string)}
                  </th>
                  <th className="text-right py-2 pl-4 text-text-muted font-medium">Change</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Weight', key: 'weight_kg', unit: 'kg', decimals: 1 },
                  { label: 'Body Fat', key: 'body_fat_pct', unit: '%', decimals: 1 },
                  { label: 'Muscle Mass', key: 'muscle_mass_kg', unit: 'kg', decimals: 1 },
                  { label: 'Fat Mass', key: 'fat_mass_kg', unit: 'kg', decimals: 1 },
                  { label: 'Visceral Fat', key: 'visceral_fat', unit: '', decimals: 0 },
                  { label: 'BMR', key: 'bmr', unit: 'kcal', decimals: 0 },
                  { label: 'BMI', key: 'bmi', unit: '', decimals: 1 },
                  { label: 'Metabolic Age', key: 'metabolic_age', unit: 'yrs', decimals: 0 },
                ].map(({ label, key, unit, decimals }) => {
                  const firstVal = first[key] as number | null;
                  const latestVal = latest[key] as number | null;
                  const delta = firstVal != null && latestVal != null ? latestVal - firstVal : null;
                  return (
                    <tr key={key} className="border-b border-border-subtle/50">
                      <td className="py-2 pr-4 text-text-primary">{label}</td>
                      <td className="text-right py-2 px-4 text-text-secondary">
                        {firstVal != null ? `${fmtNumber(firstVal, decimals)} ${unit}` : '—'}
                      </td>
                      <td className="text-right py-2 px-4 text-text-primary font-medium">
                        {latestVal != null ? `${fmtNumber(latestVal, decimals)} ${unit}` : '—'}
                      </td>
                      <td className={`text-right py-2 pl-4 font-medium ${
                        delta == null ? 'text-text-muted' : delta > 0 ? 'text-chart-amber' : delta < 0 ? 'text-chart-emerald' : 'text-text-muted'
                      }`}>
                        {delta != null ? `${delta > 0 ? '+' : ''}${fmtNumber(delta, decimals)}` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}

      {/* Forecasts */}
      {forecasts.length > 0 && (
        <ChartCard title="Trend Forecast" subtitle="Projected values based on current trajectory" className="mt-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="text-left py-2 pr-4 text-text-muted font-medium">Metric</th>
                  <th className="text-right py-2 px-4 text-text-muted font-medium">Current</th>
                  <th className="text-right py-2 px-4 text-text-muted font-medium">Rate/Month</th>
                  <th className="text-right py-2 px-4 text-text-muted font-medium">3-Month</th>
                  <th className="text-right py-2 pl-4 text-text-muted font-medium">6-Month</th>
                </tr>
              </thead>
              <tbody>
                {forecasts.map(f => (
                  <tr key={f.metric} className="border-b border-border-subtle/50">
                    <td className="py-2 pr-4 text-text-primary font-medium">{f.metric}</td>
                    <td className="text-right py-2 px-4 text-text-primary">
                      {fmtNumber(f.current, 1)} {f.unit}
                    </td>
                    <td className={`text-right py-2 px-4 font-medium ${
                      f.rate_per_month > 0 ? 'text-chart-emerald' : f.rate_per_month < 0 ? 'text-chart-rose' : 'text-text-muted'
                    }`}>
                      {f.rate_per_month > 0 ? '+' : ''}{fmtNumber(f.rate_per_month, 2)} {f.unit}
                    </td>
                    <td className="text-right py-2 px-4 text-text-secondary">
                      {fmtNumber(f.forecast_3m, 1)} {f.unit}
                    </td>
                    <td className="text-right py-2 pl-4 text-text-secondary">
                      {fmtNumber(f.forecast_6m, 1)} {f.unit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted mt-3">
            Based on {forecasts[0]?.data_points || 0} data points over {forecasts[0]?.data_span_days || 0} days. Linear extrapolation — actual results may vary.
          </p>
        </ChartCard>
      )}
    </div>
  );
}
