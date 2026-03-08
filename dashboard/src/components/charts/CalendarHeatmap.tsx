import { useMemo } from 'react';

interface Props {
  data: Record<string, unknown>[];
  dataKey: string;
  color?: string;
  weeks?: number;
}

const CELL = 14;
const GAP = 3;
const DAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', ''];

function interpolateOpacity(value: number, min: number, max: number): number {
  if (max === min) return 0.6;
  return 0.15 + 0.85 * ((value - min) / (max - min));
}

export default function CalendarHeatmap({ data, dataKey, color = '#3B82F6', weeks = 16 }: Props) {
  const { grid, monthLabels, min, max } = useMemo(() => {
    // Build value lookup
    const byDay: Record<string, number> = {};
    for (const row of data) {
      const day = row.day as string;
      const val = row[dataKey] as number;
      if (day && val != null && !isNaN(val)) byDay[day] = val;
    }

    const vals = Object.values(byDay);
    const min = vals.length ? Math.min(...vals) : 0;
    const max = vals.length ? Math.max(...vals) : 1;

    // Build grid: weeks × 7 days, ending today
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const endDay = new Date(today);
    // Go back to find the Saturday that ends the current week
    const dayOfWeek = today.getDay(); // 0=Sun
    const mondayOffset = dayOfWeek === 0 ? 6 : dayOfWeek - 1;

    const startDate = new Date(today);
    startDate.setDate(today.getDate() - mondayOffset - (weeks - 1) * 7);

    const grid: { date: string; value: number | null; col: number; row: number }[] = [];
    const monthLabels: { label: string; col: number }[] = [];
    let lastMonth = -1;

    const cursor = new Date(startDate);
    while (cursor <= endDay) {
      const iso = cursor.toISOString().split('T')[0];
      const dow = cursor.getDay();
      const row = dow === 0 ? 6 : dow - 1; // Mon=0..Sun=6
      const daysSinceStart = Math.floor((cursor.getTime() - startDate.getTime()) / 86400000);
      const col = Math.floor(daysSinceStart / 7);

      grid.push({
        date: iso,
        value: byDay[iso] ?? null,
        col,
        row,
      });

      // Month labels on first Monday of each month
      if (cursor.getMonth() !== lastMonth && row === 0) {
        monthLabels.push({
          label: cursor.toLocaleDateString('en-GB', { month: 'short' }),
          col,
        });
        lastMonth = cursor.getMonth();
      }

      cursor.setDate(cursor.getDate() + 1);
    }

    return { grid, monthLabels, min, max };
  }, [data, dataKey, weeks]);

  const labelWidth = 28;
  const headerHeight = 16;
  const svgWidth = labelWidth + weeks * (CELL + GAP);
  const svgHeight = headerHeight + 7 * (CELL + GAP);

  return (
    <div className="overflow-x-auto">
      <svg width={svgWidth} height={svgHeight} className="block">
        {/* Month labels */}
        {monthLabels.map((m, i) => (
          <text
            key={i}
            x={labelWidth + m.col * (CELL + GAP)}
            y={12}
            fontSize={10}
            fill="#71717A"
          >
            {m.label}
          </text>
        ))}

        {/* Day labels */}
        {DAY_LABELS.map((label, i) => (
          label ? (
            <text
              key={i}
              x={0}
              y={headerHeight + i * (CELL + GAP) + CELL - 2}
              fontSize={10}
              fill="#71717A"
            >
              {label}
            </text>
          ) : null
        ))}

        {/* Cells */}
        {grid.map((cell, i) => (
          <rect
            key={i}
            x={labelWidth + cell.col * (CELL + GAP)}
            y={headerHeight + cell.row * (CELL + GAP)}
            width={CELL}
            height={CELL}
            rx={3}
            fill={cell.value != null ? color : 'currentColor'}
            opacity={cell.value != null ? interpolateOpacity(cell.value, min, max) : 0.08}
          >
            <title>{`${cell.date}: ${cell.value != null ? cell.value.toLocaleString() : 'No data'}`}</title>
          </rect>
        ))}
      </svg>
    </div>
  );
}
