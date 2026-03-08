import { useState } from 'react';
import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import BarChart from '../components/charts/BarChart.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import { useTraining, useTrainingExercises, useTrainingMuscleGroups, useTrainingEstimated1RM, useTrainingIntensity, useTrainingSetTypes, useReadiness } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

export default function Training() {
  const { params } = useDateRange();
  const { data: trainingRes, isLoading } = useTraining(params);
  const { data: exercisesRes } = useTrainingExercises();
  const { data: muscleRes } = useTrainingMuscleGroups();
  const { data: readinessRes } = useReadiness(params);
  const { data: e1rmRes } = useTrainingEstimated1RM();
  const { data: intensityRes } = useTrainingIntensity();
  const { data: setTypesRes } = useTrainingSetTypes();

  const daily = trainingRes?.daily || [];
  const muscleData = muscleRes?.data || [];
  const exerciseData = exercisesRes?.data || [];

  // Unique exercise names for selector
  const exerciseNames = [...new Set(exerciseData.map(r => r.exercise as string))].sort();
  const [selectedExercise, setSelectedExercise] = useState<string>('');

  const effectiveExercise = selectedExercise || exerciseNames[0] || '';
  const exerciseHistory = exerciseData.filter(r => r.exercise === effectiveExercise);

  // KPIs
  const totalSessions = daily.length;
  const weeksSpan = daily.length >= 2
    ? Math.max((new Date(daily[daily.length - 1].day as string).getTime() - new Date(daily[0].day as string).getTime()) / (7 * 86400000), 1)
    : 1;
  const sessionsPerWeek = +(totalSessions / weeksSpan).toFixed(1);
  const avgVolume = daily.length
    ? Math.round(daily.reduce((s, r) => s + ((r.total_volume as number) || 0), 0) / weeksSpan)
    : null;

  const readinessData = readinessRes?.data || [];

  // Weekly volume
  const weeklyVolume = (() => {
    const weeks: Record<string, number> = {};
    for (const row of daily) {
      const d = new Date(row.day as string);
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const key = monday.toISOString().split('T')[0];
      weeks[key] = (weeks[key] || 0) + ((row.total_volume as number) || 0);
    }
    return Object.entries(weeks)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, volume]) => ({ day, volume: Math.round(volume) }));
  })();

  // Volume vs HRV overlay (weekly)
  const volumeHrvOverlay = (() => {
    const hrvWeeks: Record<string, { sum: number; count: number }> = {};
    for (const row of readinessData) {
      const day = row.day as string;
      if (!day) continue;
      const d = new Date(day);
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const key = monday.toISOString().split('T')[0];
      const val = row['contributors.hrv_balance'] as number;
      if (val == null || isNaN(val)) continue;
      if (!hrvWeeks[key]) hrvWeeks[key] = { sum: 0, count: 0 };
      hrvWeeks[key].sum += val;
      hrvWeeks[key].count++;
    }
    return weeklyVolume.map(wv => {
      const hrv = hrvWeeks[wv.day];
      return {
        day: wv.day,
        volume: wv.volume,
        hrv_balance: hrv ? Math.round(hrv.sum / hrv.count) : null,
      };
    });
  })();

  // Estimated 1RM trends — pivot to one column per exercise
  const e1rmData = e1rmRes?.data || [];
  const e1rmExercises = e1rmRes?.exercises || [];
  const e1rmPivoted = (() => {
    const byDay: Record<string, Record<string, unknown>> = {};
    for (const row of e1rmData) {
      const day = row.day as string;
      const exercise = row.exercise as string;
      const val = row.estimated_1rm as number;
      if (!byDay[day]) byDay[day] = { day };
      byDay[day][exercise] = Math.round(val);
    }
    return Object.values(byDay).sort((a, b) => (a.day as string).localeCompare(b.day as string));
  })();

  const e1rmColors = [chartColors.training, chartColors.recovery, chartColors.nutrition, chartColors.sleep, chartColors.warning];

  return (
    <div>
      <Header title="Training" />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6 mb-8">
        <MetricCard label="Sessions/Week" value={sessionsPerWeek} unit="avg" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
        <MetricCard label="Volume/Week" value={avgVolume} unit="kg" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
        <MetricCard label="Total Sessions" value={totalSessions} unit="" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Weekly Volume" loading={isLoading}>
          <BarChart data={weeklyVolume} dataKey="volume" color={chartColors.training} name="Volume (kg)" />
        </ChartCard>
        <ChartCard title="Muscle Group Distribution">
          <BarChart
            data={muscleData as Record<string, unknown>[]}
            dataKey="total_volume"
            xKey="muscle_group"
            color={chartColors.training}
            name="Volume (kg)"
            horizontal
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Volume vs HRV Balance" subtitle="Weekly overlay">
          <TrendChart
            data={volumeHrvOverlay}
            series={[
              { dataKey: 'volume', color: chartColors.training, name: 'Volume (kg)' },
              { dataKey: 'hrv_balance', color: chartColors.recovery, name: 'HRV Balance', type: 'line' },
            ]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Training Intensity Profile" subtitle="Volume by rep range">
          {(intensityRes?.summary || []).length > 0 ? (
            <BarChart
              data={intensityRes!.summary as Record<string, unknown>[]}
              dataKey="volume"
              xKey="zone"
              color={chartColors.training}
              name="Volume (kg)"
              horizontal
            />
          ) : (
            <p className="text-sm text-text-muted">No intensity data available</p>
          )}
        </ChartCard>
        <ChartCard title="Set Type Distribution" subtitle="All-time breakdown">
          {(setTypesRes?.data || []).length > 0 ? (
            <BarChart
              data={setTypesRes!.data as Record<string, unknown>[]}
              dataKey="sets"
              xKey="set_type"
              color={chartColors.training}
              name="Sets"
              horizontal
            />
          ) : (
            <p className="text-sm text-text-muted">No set type data available</p>
          )}
        </ChartCard>
      </div>

      {(intensityRes?.daily || []).length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:gap-6 mb-6">
          <ChartCard title="Intensity Distribution Over Time" subtitle="Daily volume by rep range">
            <StackedBar
              data={intensityRes!.daily as Record<string, unknown>[]}
              series={[
                { dataKey: 'Strength (1-5)', color: chartColors.stress, name: 'Strength (1-5 reps)' },
                { dataKey: 'Hypertrophy (6-12)', color: chartColors.training, name: 'Hypertrophy (6-12 reps)' },
                { dataKey: 'Endurance (13+)', color: chartColors.recovery, name: 'Endurance (13+ reps)' },
              ]}
            />
          </ChartCard>
        </div>
      )}

      {e1rmPivoted.length > 0 && (
        <div className="grid grid-cols-1 gap-6 mb-6">
          <ChartCard title="Estimated 1RM Trends" subtitle="Top compound exercises (Epley formula)">
            <TrendChart
              data={e1rmPivoted}
              series={e1rmExercises.map((name, i) => ({
                dataKey: name,
                color: e1rmColors[i % e1rmColors.length],
                name: `${name} (kg)`,
                type: 'line' as const,
              }))}
              showRollingToggle
            />
          </ChartCard>
        </div>
      )}

      <ChartCard title="Progressive Overload" subtitle={effectiveExercise || 'Select an exercise'}>
        <div className="mb-3">
          <select
            value={effectiveExercise}
            onChange={e => setSelectedExercise(e.target.value)}
            className="bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-border-default"
          >
            {exerciseNames.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
        <TrendChart
          data={exerciseHistory as Record<string, unknown>[]}
          series={[
            { dataKey: 'max_weight', color: chartColors.training, name: 'Max Weight (kg)', type: 'line' },
            { dataKey: 'volume', color: chartColors.sleep, name: 'Volume (kg)' },
          ]}
        />
      </ChartCard>
    </div>
  );
}
