const BASE = '/api';

export async function apiFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin);
  url.pathname = BASE + path;
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function apiReload(): Promise<{ status: string; datasets: string[] }> {
  const res = await fetch(`${BASE}/reload`, { method: 'POST' });
  if (!res.ok) throw new Error(`Reload failed: ${res.status}`);
  return res.json();
}

// Types matching API response models

export interface SparkPoint {
  date: string;
  value: number | null;
}

export interface TargetZone {
  min?: number | null;
  max?: number | null;
  label?: string | null;
}

export interface MetricSummary {
  label: string;
  value: number | null;
  unit: string;
  trend: number | null;
  sparkline: SparkPoint[];
  invert_trend?: boolean;
  target?: TargetZone | null;
}

export interface AlertOut {
  severity: string;
  title: string;
  detail: string;
  intervention: string;
  category?: string;
}

export interface OverviewData {
  metrics: MetricSummary[];
  alerts: AlertOut[];
  alert_counts: Record<string, number>;
}

export interface CorrelationItem {
  key: string;
  x_label: string;
  y_label: string;
  r_value: number | null;
  strength: string;
  points: Record<string, unknown>[];
  lag_days?: number;
  ci_low?: number | null;
  ci_high?: number | null;
  n_samples?: number;
}

export interface CorrelationsData {
  correlations: CorrelationItem[];
}

export interface PaginatedResponse<T = Record<string, unknown>> {
  data: T[];
  total: number;
  limit: number | null;
  offset: number;
}
