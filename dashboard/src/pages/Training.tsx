import { useState } from 'react';
import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import BarChart from '../components/charts/BarChart.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import { useTraining, useTrainingExercises, useTrainingMuscleGroups } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

export default function Training() {
  const { params } = useDateRange();
  const { data: trainingRes, isLoading } = useTraining(params);
  const { data: exercisesRes } = useTrainingExercises();
  const { data: muscleRes } = useTrainingMuscleGroups();

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

  return (
    <div>
      <Header title="Training" />

      <div className="grid grid-cols-3 gap-6 mb-8">
        <MetricCard label="Sessions/Week" value={sessionsPerWeek} unit="avg" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
        <MetricCard label="Volume/Week" value={avgVolume} unit="kg" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
        <MetricCard label="Total Sessions" value={totalSessions} unit="" trend={null} sparkline={[]} color={chartColors.training} loading={isLoading} />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
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
