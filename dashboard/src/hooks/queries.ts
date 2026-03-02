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

export function useTrainingExercises() {
  return useQuery<{ data: Record<string, unknown>[] }>({
    queryKey: ['training-exercises'],
    queryFn: () => apiFetch('/training/exercises'),
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

export function useAlerts() {
  return useQuery<{ alerts: AlertOut[] }>({
    queryKey: ['alerts'],
    queryFn: () => apiFetch('/alerts'),
    staleTime: 5 * 60 * 1000,
  });
}
