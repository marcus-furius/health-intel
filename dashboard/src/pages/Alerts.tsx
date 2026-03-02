import { useState } from 'react';
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

export default function Alerts() {
  const { data: alertsRes, isLoading } = useAlerts();
  const alerts = alertsRes?.alerts || [];
  const [filters, setFilters] = useState<Set<string>>(new Set(severities));

  const toggleFilter = (sev: string) => {
    setFilters(prev => {
      const next = new Set(prev);
      if (next.has(sev)) next.delete(sev);
      else next.add(sev);
      return next;
    });
  };

  const filtered = alerts.filter(a => filters.has(a.severity));

  // Group by severity
  const grouped = severities
    .filter(s => filters.has(s))
    .map(sev => ({
      severity: sev,
      label: severityLabels[sev],
      alerts: filtered.filter(a => a.severity === sev),
    }))
    .filter(g => g.alerts.length > 0);

  return (
    <div>
      <Header title="Alerts & Interventions" />

      {/* Filter toggles */}
      <div className="flex gap-2 mb-6">
        {severities.map(sev => {
          const active = filters.has(sev);
          const color = severityColors[sev];
          const count = alerts.filter(a => a.severity === sev).length;
          return (
            <button
              key={sev}
              onClick={() => toggleFilter(sev)}
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
