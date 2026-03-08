import { useState, useCallback } from 'react';

export interface Goal {
  metric: string;
  target: number;
  direction: 'above' | 'below'; // 'above' = higher is better, 'below' = lower is better
}

const STORAGE_KEY = 'health-intel-goals';

const DEFAULT_GOALS: Goal[] = [
  { metric: 'Sleep Score', target: 80, direction: 'above' },
  { metric: 'Daily Steps', target: 10000, direction: 'above' },
  { metric: 'Readiness', target: 80, direction: 'above' },
  { metric: 'Sedentary', target: 8, direction: 'below' },
];

function loadGoals(): Goal[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return DEFAULT_GOALS;
}

export function useGoals() {
  const [goals, setGoalsState] = useState<Goal[]>(loadGoals);

  const setGoals = useCallback((updater: Goal[] | ((prev: Goal[]) => Goal[])) => {
    setGoalsState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const setGoal = useCallback((metric: string, target: number, direction: 'above' | 'below' = 'above') => {
    setGoals(prev => {
      const filtered = prev.filter(g => g.metric !== metric);
      return [...filtered, { metric, target, direction }];
    });
  }, [setGoals]);

  const removeGoal = useCallback((metric: string) => {
    setGoals(prev => prev.filter(g => g.metric !== metric));
  }, [setGoals]);

  const getGoal = useCallback((metric: string): Goal | undefined => {
    return goals.find(g => g.metric === metric);
  }, [goals]);

  return { goals, setGoal, removeGoal, getGoal };
}
