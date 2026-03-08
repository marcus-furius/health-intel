import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api.ts';
import type { OverviewData, CorrelationsData, AlertOut } from '../lib/api.ts';

export function useOverview() {
  return useQuery<OverviewData>({
    queryKey: ['overview'],
    queryFn: () => apiFetch('/overview'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSleep(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['sleep', params],
    queryFn: () => apiFetch('/sleep', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useReadiness(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['readiness', params],
    queryFn: () => apiFetch('/readiness', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useActivity(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['activity', params],
    queryFn: () => apiFetch('/activity', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useStress(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['stress', params],
    queryFn: () => apiFetch('/stress', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpo2(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['spo2', params],
    queryFn: () => apiFetch('/spo2', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useHeartrate(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['heartrate', params],
    queryFn: () => apiFetch('/heartrate', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTraining(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[]; daily: Record<string, unknown>[] }>({
    queryKey: ['training', params],
    queryFn: () => apiFetch('/training', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useReadinessContributors(params?: Record<string, string>) {
  return useQuery<{ contributors: { contributor: string; value: number }[]; daily: Record<string, unknown>[] }>({
    queryKey: ['readiness-contributors', params],
    queryFn: () => apiFetch('/readiness/contributors', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSleepContributors(params?: Record<string, string>) {
  return useQuery<{ contributors: { contributor: string; value: number }[]; daily: Record<string, unknown>[] }>({
    queryKey: ['sleep-contributors', params],
    queryFn: () => apiFetch('/sleep/contributors', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingIntensity() {
  return useQuery<{ summary: Record<string, unknown>[]; daily: Record<string, unknown>[] }>({
    queryKey: ['training-intensity'],
    queryFn: () => apiFetch('/training/intensity'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingSetTypes() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['training-set-types'],
    queryFn: () => apiFetch('/training/set-types'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingExercises() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['training-exercises'],
    queryFn: () => apiFetch('/training/exercises'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingEstimated1RM() {
  return useQuery<{ data: Record<string, unknown>[]; exercises: string[] }>({
    queryKey: ['training-estimated-1rm'],
    queryFn: () => apiFetch('/training/estimated-1rm'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingMuscleGroups() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['training-muscle-groups'],
    queryFn: () => apiFetch('/training/muscle-groups'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useNutrition(params?: Record<string, string>) {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['nutrition', params],
    queryFn: () => apiFetch('/nutrition', params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useBodyComposition() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['body-composition'],
    queryFn: () => apiFetch('/body-composition'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useWeight() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['weight'],
    queryFn: () => apiFetch('/weight'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCorrelations() {
  return useQuery<CorrelationsData>({
    queryKey: ['correlations'],
    queryFn: () => apiFetch('/correlations'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDigest() {
  return useQuery<{
    current_week: string;
    previous_week: string;
    items: { label: string; unit: string; current: number | null; previous: number | null; delta: number | null }[];
  }>({
    queryKey: ['digest'],
    queryFn: () => apiFetch('/digest'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCompare(aStart: string, aEnd: string, bStart: string, bEnd: string, enabled: boolean) {
  return useQuery<{ comparisons: { label: string; unit: string; period_a: number | null; period_b: number | null; delta: number | null; improved: boolean | null }[] }>({
    queryKey: ['compare', aStart, aEnd, bStart, bEnd],
    queryFn: () => apiFetch('/compare', { a_start: aStart, a_end: aEnd, b_start: bStart, b_end: bEnd }),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useRecords() {
  return useQuery<{ records: { category: string; label: string; value: number; unit: string; date: string | null }[] }>({
    queryKey: ['records'],
    queryFn: () => apiFetch('/records'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAlerts() {
  return useQuery<{ alerts: AlertOut[] }>({
    queryKey: ['alerts'],
    queryFn: () => apiFetch('/alerts'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useStreaks() {
  return useQuery<{ streaks: { metric: string; target: string; current: number; best: number; unit: string }[] }>({
    queryKey: ['streaks'],
    queryFn: () => apiFetch('/streaks'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrainingRecommendation() {
  return useQuery<{
    score: number | null;
    intensity: string;
    detail: string;
    components?: { readiness: number; hrv_balance: number; load_factor: number; recent_volume: number };
  }>({
    queryKey: ['training-recommendation'],
    queryFn: () => apiFetch('/training/recommendation'),
    staleTime: 5 * 60 * 1000,
  });
}

export function useInterventionImpact(date: string, window: number, enabled: boolean) {
  return useQuery<{
    metrics: { label: string; unit: string; before: number | null; after: number | null; delta: number | null; improved: boolean | null }[];
    window_days: number;
  }>({
    queryKey: ['intervention-impact', date, window],
    queryFn: () => apiFetch('/intervention-impact', { intervention_date: date, window: String(window) }),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useForecasts() {
  return useQuery<{
    forecasts: {
      metric: string; unit: string; current: number;
      rate_per_month: number; direction: string;
      data_span_days: number; data_points: number;
      forecast_3m: number; forecast_6m: number;
    }[];
  }>({
    queryKey: ['forecasts'],
    queryFn: () => apiFetch('/forecasts'),
    staleTime: 5 * 60 * 1000,
  });
}
