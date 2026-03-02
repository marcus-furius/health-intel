import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import { useBodyComposition, useWeight } from '../hooks/queries.ts';
import { fmtNumber, fmtDateLong } from '../lib/format.ts';
import { chartColors } from '../lib/colors.ts';

export default function BodyComposition() {
  const { data: bodyRes, isLoading } = useBodyComposition();
  const { data: weightRes } = useWeight();

  const scans = bodyRes?.data || [];
  const latest = scans.length ? scans[scans.length - 1] : null;
  const first = scans.length >= 2 ? scans[0] : null;
  const weightData = weightRes?.data || [];

  return (
    <div>
      <Header title="Body Composition" />

      <div className="grid grid-cols-5 gap-6 mb-8">
        <MetricCard label="Weight" value={latest?.weight_kg as number} unit="kg" trend={null} sparkline={[]} color="#A1A1AA" loading={isLoading} />
        <MetricCard label="Body Fat" value={latest?.body_fat_pct as number} unit="%" trend={null} sparkline={[]} color={chartColors.warning} loading={isLoading} />
        <MetricCard label="Muscle Mass" value={latest?.muscle_mass_kg as number} unit="kg" trend={null} sparkline={[]} color={chartColors.recovery} loading={isLoading} />
        <MetricCard label="Visceral Fat" value={latest?.visceral_fat as number} unit="rating" trend={null} sparkline={[]} color={chartColors.stress} loading={isLoading} />
        <MetricCard label="Metabolic Age" value={latest?.metabolic_age as number} unit="yrs" trend={null} sparkline={[]} color={chartColors.sleep} loading={isLoading} />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
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

      <div className="grid grid-cols-2 gap-6 mb-6">
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
  );
}
