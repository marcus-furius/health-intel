import type { ReactNode } from 'react';
import { Download } from 'lucide-react';
import Skeleton from './Skeleton.tsx';

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode;
  loading?: boolean;
  className?: string;
  exportData?: Record<string, unknown>[];
  headerAction?: ReactNode;
}

function downloadCsv(data: Record<string, unknown>[], filename: string) {
  if (!data.length) return;
  const keys = Object.keys(data[0]);
  const rows = [keys.join(',')];
  for (const row of data) {
    rows.push(keys.map(k => {
      const v = row[k];
      if (v == null) return '';
      const s = String(v);
      return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(','));
  }
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ChartCard({ title, subtitle, children, loading, className = '', exportData, headerAction }: Props) {
  return (
    <div className={`bg-bg-card border border-border-subtle rounded-2xl p-7 animate-card-enter transition-all hover:border-border-default hover:shadow-lg hover:shadow-[#0F0E0D]/10 ${className}`}>
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-lg font-serif text-text-primary">{title}</h3>
          {subtitle && <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {headerAction}
          {exportData && exportData.length > 0 && (
            <button
              onClick={() => downloadCsv(exportData, title.toLowerCase().replace(/\s+/g, '_'))}
              className="no-print text-text-muted hover:text-text-secondary transition-colors p-1"
              title="Export CSV"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-48 w-full" />
        </div>
      ) : children}
    </div>
  );
}
