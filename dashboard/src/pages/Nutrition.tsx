import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import StackedBar from '../components/charts/StackedBar.tsx';
import { useNutrition, useBodyComposition, useWeight } from '../hooks/queries.ts';
import { useDateRange } from '../hooks/useDateRange.ts';
import { chartColors } from '../lib/colors.ts';

export default function Nutrition() {
  const { params } = useDateRange();
  const { data: nutrRes, isLoading } = useNutrition(params);
  const { data: bodyRes } = useBodyComposition();
  const { data: weightRes } = useWeight();

  const data = nutrRes?.data || [];
  const logged = data.filter(r => ((r.calories as number) || 0) > 0);

  const avgCalories = logged.length
    ? Math.round(logged.reduce((s, r) => s + ((r.calories as number) || 0), 0) / logged.length)
    : null;
  const avgProtein = logged.length
    ? Math.round(logged.reduce((s, r) => s + ((r.protein as number) || 0), 0) / logged.length)
    : null;

  const latestWeight = bodyRes?.data?.length
    ? (bodyRes.data[bodyRes.data.length - 1].weight_kg as number)
    : null;
  const proteinPerKg = avgProtein && latestWeight ? +(avgProtein / latestWeight).toFixed(1) : null;

  const compliance = data.length ? Math.round((logged.length / data.length) * 100) : null;

  // Caloric balance: we don't have TDEE here, just show as intake
  const macroData = logged.map(r => ({
    day: r.day as string,
    protein: ((r.protein as number) || 0) * 4,
    carbs: ((r.carbohydrates as number) || 0) * 4,
    fat: ((r.fat as number) || 0) * 9,
  }));

  // Calories vs Weight overlay (weekly avg)
  const weightData = weightRes?.data || [];
  const caloriesWeightOverlay = (() => {
    const calWeeks: Record<string, { sum: number; count: number }> = {};
    for (const row of logged) {
      const day = row.day as string;
      if (!day) continue;
      const d = new Date(day);
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      const key = monday.toISOString().split('T')[0];
      const val = row.calories as number;
      if (val == null) continue;
      if (!calWeeks[key]) calWeeks[key] = { sum: 0, count: 0 };
      calWeeks[key].sum += val;
      calWeeks[key].count++;
    }
    const wtByDay: Record<string, number> = {};
    for (const row of weightData) {
      wtByDay[row.day as string] = row.weight_kg as number;
    }
    // Match weight to week (find nearest weight within the week)
    return Object.entries(calWeeks)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([weekDay, { sum, count }]) => {
        const weekStart = new Date(weekDay);
        let nearestWt: number | null = null;
        for (let i = 0; i < 7; i++) {
          const d = new Date(weekStart);
          d.setDate(weekStart.getDate() + i);
          const key = d.toISOString().split('T')[0];
          if (wtByDay[key] != null) { nearestWt = wtByDay[key]; break; }
        }
        return {
          day: weekDay,
          avg_calories: Math.round(sum / count),
          weight_kg: nearestWt,
        };
      });
  })();

  // Protein/kg trend
  const proteinTrend = latestWeight
    ? logged.map(r => ({
        day: r.day as string,
        protein_per_kg: +((r.protein as number) / latestWeight).toFixed(2),
        target_low: 1.6,
        target_high: 2.2,
      }))
    : [];

  return (
    <div>
      <Header title="Nutrition" />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 mb-8">
        <MetricCard label="Avg Calories" value={avgCalories} unit="kcal" trend={null} sparkline={[]} color={chartColors.nutrition} loading={isLoading} />
        <MetricCard label="Protein/Day" value={avgProtein} unit="g" trend={null} sparkline={[]} color={chartColors.nutrition} loading={isLoading} />
        <MetricCard label="Protein/kg" value={proteinPerKg} unit="g/kg" trend={null} sparkline={[]} color={proteinPerKg && proteinPerKg >= 1.6 ? chartColors.recovery : chartColors.warning} loading={isLoading} target={{ min: 1.6, max: 2.2 }} />
        <MetricCard label="Compliance" value={compliance} unit="%" trend={null} sparkline={[]} color={compliance && compliance >= 80 ? chartColors.recovery : chartColors.warning} loading={isLoading} target={{ min: 80 }} />
        <MetricCard label="Weight" value={latestWeight} unit="kg" trend={null} sparkline={[]} color="#A1A1AA" loading={isLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Calorie Trend" loading={isLoading}>
          <TrendChart
            data={data as Record<string, unknown>[]}
            series={[{ dataKey: 'calories', color: chartColors.nutrition, name: 'Calories (kcal)' }]}
            showRollingToggle
          />
        </ChartCard>
        <ChartCard title="Macro Split" subtitle="Calories from macros">
          <StackedBar
            data={macroData}
            series={[
              { dataKey: 'protein', color: chartColors.recovery, name: 'Protein' },
              { dataKey: 'carbs', color: chartColors.nutrition, name: 'Carbs' },
              { dataKey: 'fat', color: chartColors.warning, name: 'Fat' },
            ]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 mb-6">
        <ChartCard title="Protein per kg Bodyweight" subtitle="Target: 1.6–2.2 g/kg">
          {proteinTrend.length > 0 ? (
            <TrendChart
              data={proteinTrend}
              series={[
                { dataKey: 'protein_per_kg', color: chartColors.nutrition, name: 'Protein (g/kg)', type: 'line' },
                { dataKey: 'target_low', color: chartColors.recovery, name: 'Min Target', type: 'line' },
                { dataKey: 'target_high', color: chartColors.recovery, name: 'Max Target', type: 'line' },
              ]}
              domain={[0, 'auto']}
            />
          ) : (
            <p className="text-sm text-text-muted">Need body composition data for protein/kg calculation</p>
          )}
        </ChartCard>
        <ChartCard title="Daily Macros (grams)">
          <TrendChart
            data={logged as Record<string, unknown>[]}
            series={[
              { dataKey: 'protein', color: chartColors.recovery, name: 'Protein (g)', type: 'line' },
              { dataKey: 'carbohydrates', color: chartColors.nutrition, name: 'Carbs (g)', type: 'line' },
              { dataKey: 'fat', color: chartColors.warning, name: 'Fat (g)', type: 'line' },
            ]}
            showRollingToggle
          />
        </ChartCard>
      </div>

      {caloriesWeightOverlay.some(r => r.weight_kg != null) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
          <ChartCard title="Calories vs Weight" subtitle="Weekly overlay">
            <TrendChart
              data={caloriesWeightOverlay}
              series={[
                { dataKey: 'avg_calories', color: chartColors.nutrition, name: 'Avg Calories (kcal)' },
                { dataKey: 'weight_kg', color: '#A1A1AA', name: 'Weight (kg)', type: 'line' },
              ]}
            />
          </ChartCard>
        </div>
      )}
    </div>
  );
}
