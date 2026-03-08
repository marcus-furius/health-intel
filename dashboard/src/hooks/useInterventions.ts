import { useState, useCallback } from 'react';

export interface Intervention {
  id: string;
  label: string;
  date: string; // ISO date YYYY-MM-DD
  category: 'sleep' | 'nutrition' | 'training' | 'supplement' | 'lifestyle';
}

const STORAGE_KEY = 'health-intel-interventions';

function loadInterventions(): Intervention[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return [];
}

export function useInterventions() {
  const [interventions, setInterventionsState] = useState<Intervention[]>(loadInterventions);

  const save = useCallback((items: Intervention[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    setInterventionsState(items);
  }, []);

  const addIntervention = useCallback((label: string, date: string, category: Intervention['category']) => {
    const item: Intervention = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      label,
      date,
      category,
    };
    save([...loadInterventions(), item]);
  }, [save]);

  const removeIntervention = useCallback((id: string) => {
    save(loadInterventions().filter(i => i.id !== id));
  }, [save]);

  return { interventions, addIntervention, removeIntervention };
}
