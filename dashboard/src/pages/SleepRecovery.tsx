import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import BarChart from '../components/charts/BarChart.tsx';
import { useSleep, useReadiness, useSpo2, useStress, useHeartrate, useSleepContributors, useReadinessContributors } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

export default function SleepRecovery() {
  const { params } = useDateRange();
  const { data: sleepRes, isLoading: sleepLoading } = useSleep(params);
  const { data: readinessRes, isLoading: readinessLoading } = useReadiness(params);
  const { data: spo2Res, isLoading: spo2Loading } = useSpo2(params);
  const { data: stressRes } = useStress(params);
  const { data: hrRes, isLoading: hrLoading } = useHeartrate(params);
  const { data: sleepContribRes } = useSleepContributors(params);
  const { data: readinessContribRes } = useReadinessContributors(params);

  const sleepData = sleepRes?.data || [];
  const readinessData = readinessRes?.data || [];
  const spo2Data = spo2Res?.data || [];
  const stressData = stressRes?.data || [];
  const hrData = hrRes?.data || [];

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
  const avgRhr = hrData.length
    ? (() => {
        const vals = hrData.map(r => r.hr_min as number).filter(v => v != null);
        return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
      })()
    : null;

  // Deep sleep % and REM %
  const sleepWithStages = sleepData.filter(r => r.total_sleep_duration != null && (r.total_sleep_duration as number) > 0);
  const avgDeepPct = sleepWithStages.length
    ? (() => {
        const vals = sleepWithStages.map(r => ((r.deep_sleep_duration as number) || 0) / (r.total_sleep_duration as number) * 100);
        return +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
      })()
    : null;
  const avgRemPct = sleepWithStages.length
    ? (() => {
        const vals = sleepWithStages.map(r => ((r.rem_sleep_duration as number) || 0) / (r.total_sleep_duration as number) * 100);
        return +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
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

  // Sleep latency trend (from contributors)
  const sleepContribDaily = sleepContribRes?.daily || [];

  // Contributor averages
  const sleepContribs = sleepContribRes?.contributors || [];
  const readinessContribs = readinessContribRes?.contributors || [];

  return (
    <div>
      <Header title="Sleep & Recovery" />

      {/* KPIs — two rows: 4 + 3 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5 lg:gap-7 mb-5 animate-stagger">
        <MetricCard label="Sleep Score" value={avgSleep} unit="avg" trend={null} sparkline={[]} color={chartColors.sleep} loading={sleepLoading} />
        <MetricCard label="Readiness" value={avgReadiness} unit="avg" trend={null} sparkline={[]} color={chartColors.recovery} loading={readinessLoading} />
        <MetricCard label="HRV Balance" value={avgHrv} unit="avg" trend={null} sparkline={[]} color={chartColors.recovery} loading={readinessLoading} />
        <MetricCard label="Deep Sleep" value={avgDeepPct} unit="%" trend={null} sparkline={[]} color="#8B7BB5" loading={sleepLoading} target={{ min: 20, max: 25 }} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-5 lg:gap-7 mb-10 animate-stagger">
        <MetricCard label="REM Sleep" value={avgRemPct} unit="%" trend={null} sparkline={[]} color={chartColors.sleep} loading={sleepLoading} target={{ min: 18, max: 25 }} />
        <MetricCard label="Resting HR" value={avgRhr} unit="bpm" trend={null} sparkline={[]} color={chartColors.stress} loading={hrLoading} invertTrend />
        <MetricCard label="SpO2" value={avgSpo2} unit="%" trend={null} sparkline={[]} color={chartColors.spo2} loading={spo2Loading} />
      </div>

      {/* Score trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Sleep Score Trend" loading={sleepLoading}>
          <TrendChart
            data={sleepData as Record<string, unknown>[]}
            series={[{ dataKey: 'score', color: chartColors.sleep, name: 'Sleep Score' }]}
            showRollingToggle
          />
        </ChartCard>
        <ChartCard title="Readiness Trend" loading={readinessLoading}>
          <TrendChart
            data={readinessData as Record<string, unknown>[]}
            series={[{ dataKey: 'score', color: chartColors.recovery, name: 'Readiness' }]}
            showRollingToggle
          />
        </ChartCard>
      </div>

      {/* Contributor breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Sleep Score Drivers" subtitle="Average contributor scores">
          {sleepContribs.length > 0 ? (
            <BarChart
              data={sleepContribs}
              dataKey="value"
              xKey="contributor"
              color={chartColors.sleep}
              name="Score"
              horizontal
            />
          ) : (
            <p className="text-sm text-text-muted">No contributor data available</p>
          )}
        </ChartCard>
        <ChartCard title="Readiness Score Drivers" subtitle="Average contributor scores">
          {readinessContribs.length > 0 ? (
            <BarChart
              data={readinessContribs}
              dataKey="value"
              xKey="contributor"
              color={chartColors.recovery}
              name="Score"
              horizontal
            />
          ) : (
            <p className="text-sm text-text-muted">No contributor data available</p>
          )}
        </ChartCard>
      </div>

      {/* HRV & RHR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="HRV Balance" loading={readinessLoading}>
          <TrendChart
            data={readinessData as Record<string, unknown>[]}
            series={[{ dataKey: 'contributors.hrv_balance', color: chartColors.recovery, name: 'HRV Balance', type: 'line' }]}
            showRollingToggle
          />
        </ChartCard>
        <ChartCard title="Resting Heart Rate" loading={hrLoading}>
          <TrendChart
            data={hrData as Record<string, unknown>[]}
            series={[{ dataKey: 'hr_min', color: chartColors.stress, name: 'RHR (bpm)', type: 'line' }]}
            showRollingToggle
          />
        </ChartCard>
      </div>

      {/* Sleep stages & latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Sleep Stages" subtitle="Minutes per night">
          {stageData.length > 0 ? (
            <StackedBar
              data={stageData}
              series={[
                { dataKey: 'deep', color: '#8B7BB5', name: 'Deep' },
                { dataKey: 'rem', color: chartColors.sleep, name: 'REM' },
                { dataKey: 'light', color: '#A69F95', name: 'Light' },
                { dataKey: 'awake', color: chartColors.stress, name: 'Awake' },
              ]}
            />
          ) : (
            <p className="text-sm text-text-muted">No sleep stage data available</p>
          )}
        </ChartCard>
        <ChartCard title="Sleep Latency" subtitle="Contributor score (higher = fell asleep faster)">
          {sleepContribDaily.length > 0 ? (
            <TrendChart
              data={sleepContribDaily}
              series={[{ dataKey: 'contributors.latency', color: chartColors.sleep, name: 'Latency Score', type: 'line' }]}
              showRollingToggle
            />
          ) : (
            <p className="text-sm text-text-muted">No latency data available</p>
          )}
        </ChartCard>
      </div>

      {/* SpO2 & Stress */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7">
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
