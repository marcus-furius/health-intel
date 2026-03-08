import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronUp, AlertTriangle, AlertCircle, Info, CheckCircle, ArrowRight } from 'lucide-react';
import { severityColors } from '../../lib/colors.ts';
import type { AlertOut } from '../../lib/api.ts';

const severityIcons: Record<string, typeof AlertTriangle> = {
  high: AlertTriangle,
  medium: AlertCircle,
  low: Info,
  positive: CheckCircle,
};

const categoryRoutes: Record<string, string> = {
  sleep: '/sleep',
  body: '/body',
  training: '/training',
  nutrition: '/nutrition',
  activity: '/',
  correlations: '/correlations',
};

interface Props {
  alert: AlertOut;
}

export default function AlertCard({ alert }: Props) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();
  const Icon = severityIcons[alert.severity] || Info;
  const color = severityColors[alert.severity] || '#71717A';
  const route = alert.category ? categoryRoutes[alert.category] : undefined;

  return (
    <div
      className="bg-bg-card border border-border-subtle rounded-xl p-5 transition-all hover:border-border-default"
      style={{ borderLeftWidth: 3, borderLeftColor: color }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-start justify-between w-full text-left gap-3"
      >
        <div className="flex items-start gap-3 min-w-0">
          <Icon className="w-5 h-5 mt-0.5 shrink-0" style={{ color }} />
          <div className="min-w-0">
            <h4 className="font-medium text-text-primary">{alert.title}</h4>
            <p className="text-sm text-text-secondary mt-1">{alert.detail}</p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted shrink-0 mt-1" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted shrink-0 mt-1" />
        )}
      </button>
      {expanded && (
        <div className="mt-4 ml-8 pl-3 border-l-2 border-border-subtle">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Recommended Actions</p>
          <div className="text-sm text-text-secondary space-y-1 whitespace-pre-line">
            {alert.intervention}
          </div>
          {route && (
            <button
              onClick={(e) => { e.stopPropagation(); navigate(route); }}
              className="flex items-center gap-1.5 mt-3 text-xs font-medium text-chart-blue hover:underline"
            >
              View details <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
