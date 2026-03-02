import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import { useSleep, useReadiness, useSpo2, useStress } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

export default function SleepRecovery() {
  const { params } = useDateRange();
  const { data: sleepRes, isLoading: sleepLoading } = useSleep(params);
  const { data: readinessRes, isLoading: readinessLoading } = useReadiness(params);
  const { data: spo2Res, isLoading: spo2Loading } = useSpo2(params);
  const { data: stressRes } = useStress(params);

  const sleepData = sleepRes?.data || [];
  const readinessData = readinessRes?.data || [];
  const spo2Data = spo2Res?.data || [];
  const stressData = stressRes?.data || [];

  const avgSleep = sleepData.length
    ? Math.round(sleepData.reduce((s, r) => s + ((r.score as number) || 0), 0) / sleepData.length)
    : null;
  const avgReadiness = readinessData.length
    ? Math.round(readinessData.reduce((s, r) => s + ((r.score as number) || 0), 0) / readinessData.length)
    : null;
  const avgHrv = readinessData.length
    ? (() => {
        const vals = readinessData
          .map(r => r['contributors.hrv_balance'] as number)
          .filter(v => v != null);
        return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
      })()
    : null;
  const avgSpo2 = spo2Data.length
    ? (() => {
        const vals = spo2Data
          .map(r => r['spo2_percentage.average'] as number)
          .filter(v => v != null);
        return vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : null;
      })()
    : null;

  // Build sleep stage data
  const stageData = sleepData
    .filter(r => r.deep_sleep_duration != null)
    .map(r => ({
      day: r.day as string,
      deep: Math.round(((r.deep_sleep_duration as number) || 0) / 60),
      rem: Math.round(((r.rem_sleep_duration as number) || 0) / 60),
      light: Math.round(((r.light_sleep_duration as number) || 0) / 60),
      awake: Math.round(((r.awake_time as number) || 0) / 60),
    }));

  return (
    <div>
      <Header title="Sleep & Recovery" />

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <MetricCard label="Sleep Score" value={avgSleep} unit="avg" trend={null} sparkline={[]} color={chartColors.sleep} loading={sleepLoading} />
        <MetricCard label="Readiness" value={avgReadiness} unit="avg" trend={null} sparkline={[]} color={chartColors.recovery} loading={readinessLoading} />
        <MetricCard label="HRV Balance" value={avgHrv} unit="avg" trend={null} sparkline={[]} color={chartColors.recovery} loading={readinessLoading} />
        <MetricCard label="SpO2" value={avgSpo2} unit="%" trend={null} sparkline={[]} color={chartColors.spo2} loading={spo2Loading} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <ChartCard title="Sleep Score Trend" loading={sleepLoading}>
          <TrendChart
            data={sleepData as Record<string, unknown>[]}
            series={[{ dataKey: 'score', color: chartColors.sleep, name: 'Sleep Score' }]}
          />
        </ChartCard>
        <ChartCard title="Readiness Trend" loading={readinessLoading}>
          <TrendChart
            data={readinessData as Record<string, unknown>[]}
            series={[{ dataKey: 'score', color: chartColors.recovery, name: 'Readiness' }]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <ChartCard title="HRV Balance" loading={readinessLoading}>
          <TrendChart
            data={readinessData as Record<string, unknown>[]}
            series={[{ dataKey: 'contributors.hrv_balance', color: chartColors.recovery, name: 'HRV Balance', type: 'line' }]}
          />
        </ChartCard>
        <ChartCard title="Sleep Stages" subtitle="Minutes per night">
          {stageData.length > 0 ? (
            <StackedBar
              data={stageData}
              series={[
                { dataKey: 'deep', color: '#6366F1', name: 'Deep' },
                { dataKey: 'rem', color: chartColors.sleep, name: 'REM' },
                { dataKey: 'light', color: '#94A3B8', name: 'Light' },
                { dataKey: 'awake', color: chartColors.stress, name: 'Awake' },
              ]}
            />
          ) : (
            <p className="text-sm text-text-muted">No sleep stage data available</p>
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <ChartCard title="SpO2 Trend" subtitle="95% threshold" loading={spo2Loading}>
          <TrendChart
            data={spo2Data as Record<string, unknown>[]}
            series={[{ dataKey: 'spo2_percentage.average', color: chartColors.spo2, name: 'SpO2 %', type: 'line' }]}
            domain={[90, 100]}
          />
        </ChartCard>
        <ChartCard title="Stress vs Recovery" subtitle="Daily minutes">
          <StackedBar
            data={stressData as Record<string, unknown>[]}
            series={[
              { dataKey: 'recovery_high', color: chartColors.recovery, name: 'Recovery' },
              { dataKey: 'stress_high', color: chartColors.stress, name: 'Stress' },
            ]}
          />
        </ChartCard>
      </div>
    </div>
  );
}
