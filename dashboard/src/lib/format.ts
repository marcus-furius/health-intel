export function fmtNumber(value: number | null | undefined, decimals = 0): string {
  if (value == null || isNaN(value)) return '—';
  return value.toLocaleString('en-GB', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function fmtDate(dateStr: unknown): string {
  const d = new Date(String(dateStr));
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

export function fmtDateLong(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function fmtWeek(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

export function trendArrow(trend: number | null | undefined): string {
  if (trend == null) return '';
  if (trend > 0.1) return '↑';
  if (trend < -0.1) return '↓';
  return '→';
}

export function trendColor(trend: number | null | undefined): string {
  if (trend == null) return 'text-text-muted';
  if (trend > 0.1) return 'text-chart-emerald';
  if (trend < -0.1) return 'text-chart-rose';
  return 'text-text-muted';
}
