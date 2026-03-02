import type { ReactNode } from 'react';
import Skeleton from './Skeleton.tsx';

interface Props {
  title: string;
  subtitle?: string;
  children: ReactNode;
  loading?: boolean;
  className?: string;
}

export default function ChartCard({ title, subtitle, children, loading, className = '' }: Props) {
  return (
    <div className={`bg-bg-card border border-border-subtle rounded-xl p-6 transition-all hover:border-border-default hover:shadow-lg hover:shadow-black/5 ${className}`}>
      <div className="mb-4">
        <h3 className="text-lg font-medium text-text-primary">{title}</h3>
        {subtitle && <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-48 w-full" />
        </div>
      ) : children}
    </div>
  );
}
