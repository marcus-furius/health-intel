import { useState, useMemo } from 'react';
import Header from '../components/layout/Header.tsx';
import AlertCard from '../components/ui/AlertCard.tsx';
import Skeleton from '../components/ui/Skeleton.tsx';
import { useAlerts } from '../hooks/queries.ts';
import { severityColors } from '../lib/colors.ts';

const severities = ['high', 'medium', 'low', 'positive'] as const;
const severityLabels: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  positive: 'Positive',
};

const categoryLabels: Record<string, string> = {
  sleep: 'Sleep & Recovery',
  body: 'Body Composition',
  training: 'Training',
  nutrition: 'Nutrition',
  activity: 'Activity',
  correlations: 'Cross-Source',
};

export default function Alerts() {
  const { data: alertsRes, isLoading } = useAlerts();
  const alerts = alertsRes?.alerts || [];
  const [sevFilters, setSevFilters] = useState<Set<string>>(new Set(severities));
  const [catFilters, setCatFilters] = useState<Set<string> | null>(null); // null = all

  const categories = useMemo(() => {
    const cats = new Set<string>();
    alerts.forEach(a => { if (a.category) cats.add(a.category); });
    return Array.from(cats).sort();
  }, [alerts]);

  const toggleSev = (sev: string) => {
    setSevFilters(prev => {
      const next = new Set(prev);
      if (next.has(sev)) next.delete(sev);
      else next.add(sev);
      return next;
    });
  };

  const toggleCat = (cat: string) => {
    setCatFilters(prev => {
      if (prev === null) {
        // First click: select only this category
        return new Set([cat]);
      }
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      // If all deselected, revert to "all"
      return next.size === 0 ? null : next;
    });
  };

  const filtered = alerts.filter(a =>
    sevFilters.has(a.severity) &&
    (catFilters === null || catFilters.has(a.category || ''))
  );

  // Group by severity
  const grouped = severities
    .filter(s => sevFilters.has(s))
    .map(sev => ({
      severity: sev,
      label: severityLabels[sev],
      alerts: filtered.filter(a => a.severity === sev),
    }))
    .filter(g => g.alerts.length > 0);

  return (
    <div>
      <Header title="Alerts & Interventions" />

      {/* Severity filter toggles */}
      <div className="flex flex-wrap gap-2 mb-3">
        {severities.map(sev => {
          const active = sevFilters.has(sev);
          const color = severityColors[sev];
          const count = alerts.filter(a => a.severity === sev).length;
          return (
            <button
              key={sev}
              onClick={() => toggleSev(sev)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                active ? 'border-border-default' : 'border-transparent opacity-40'
              }`}
              style={{
                backgroundColor: active ? `${color}15` : 'transparent',
                color: active ? color : '#71717A',
              }}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              {severityLabels[sev]} ({count})
            </button>
          );
        })}
      </div>

      {/* Category filter toggles */}
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setCatFilters(null)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              catFilters === null ? 'border-border-default bg-bg-elevated text-text-primary' : 'border-transparent text-text-muted opacity-60'
            }`}
          >
            All
          </button>
          {categories.map(cat => {
            const active = catFilters === null || catFilters.has(cat);
            const count = alerts.filter(a => a.category === cat).length;
            return (
              <button
                key={cat}
                onClick={() => toggleCat(cat)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                  active && catFilters !== null ? 'border-border-default bg-bg-elevated text-text-primary' : !active ? 'border-transparent text-text-muted opacity-40' : 'border-transparent text-text-secondary'
                }`}
              >
                {categoryLabels[cat] || cat} ({count})
              </button>
            );
          })}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-bg-card border border-border-subtle rounded-xl p-5">
              <Skeleton className="h-5 w-48 mb-2" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-text-muted">No alerts match the current filter.</p>
      ) : (
        <div className="space-y-6">
          {grouped.map(({ severity, label, alerts: groupAlerts }) => (
            <div key={severity}>
              <h2 className="text-sm font-medium uppercase tracking-wide mb-3" style={{ color: severityColors[severity] }}>
                {label} ({groupAlerts.length})
              </h2>
              <div className="space-y-3">
                {groupAlerts.map((a, i) => (
                  <AlertCard key={`${severity}-${i}`} alert={a} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
