import { severityColors } from '../../lib/colors.ts';

interface Props {
  label: string;
  variant?: string;
  className?: string;
}

export default function Badge({ label, variant, className = '' }: Props) {
  const color = variant ? severityColors[variant] || '#71717A' : '#71717A';
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${className}`}
      style={{ color, backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
    >
      {label}
    </span>
  );
}
