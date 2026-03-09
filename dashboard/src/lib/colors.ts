export const colors = {
  gold: '#C9A96E',
  sage: '#7BA693',
  terracotta: '#C17858',
  rose: '#B85C5C',
  violet: '#8B7BB5',
  steel: '#5C8BB8',
  teal: '#4BA3A3',
} as const;

export const accent = '#C9A96E';
export const accentHover = '#D4B87D';

export const chartColors = {
  sleep: colors.gold,
  recovery: colors.sage,
  warning: colors.terracotta,
  stress: colors.rose,
  training: colors.violet,
  nutrition: colors.teal,
  spo2: colors.steel,
} as const;

export const severityColors: Record<string, string> = {
  high: colors.rose,
  medium: colors.terracotta,
  low: colors.steel,
  positive: colors.sage,
};
