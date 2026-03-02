export const colors = {
  blue: '#3B82F6',
  emerald: '#10B981',
  amber: '#F59E0B',
  rose: '#F43F5E',
  violet: '#8B5CF6',
  orange: '#F97316',
  cyan: '#06B6D4',
} as const;

export const chartColors = {
  sleep: colors.blue,
  recovery: colors.emerald,
  warning: colors.amber,
  stress: colors.rose,
  training: colors.violet,
  nutrition: colors.orange,
  spo2: colors.cyan,
} as const;

export const severityColors: Record<string, string> = {
  high: colors.rose,
  medium: colors.amber,
  low: colors.blue,
  positive: colors.emerald,
};
