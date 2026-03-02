import { useState, useRef, useEffect } from 'react';
import { Calendar } from 'lucide-react';
import type { DateRange } from '../../hooks/useDateRange.ts';
import { fmtDateLong } from '../../lib/format.ts';

const presets = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 180 },
  { label: 'All time', days: 0 },
];

interface Props {
  value: DateRange;
  onChange: (r: DateRange) => void;
}

export default function DateRangePicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const label = value.start && value.end
    ? `${fmtDateLong(value.start)} – ${fmtDateLong(value.end)}`
    : 'All time';

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 text-sm bg-bg-elevated border border-border-subtle rounded-lg text-text-secondary hover:text-text-primary hover:border-border-default transition-colors"
      >
        <Calendar className="w-4 h-4" />
        {label}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 bg-bg-card border border-border-default rounded-xl shadow-xl shadow-black/20 p-3 z-30 min-w-[160px]">
          {presets.map(({ label, days }) => (
            <button
              key={label}
              onClick={() => {
                if (days === 0) {
                  onChange({ start: null, end: null });
                } else {
                  const end = new Date();
                  const start = new Date();
                  start.setDate(start.getDate() - days);
                  onChange({
                    start: start.toISOString().split('T')[0],
                    end: end.toISOString().split('T')[0],
                  });
                }
                setOpen(false);
              }}
              className="block w-full text-left px-3 py-2 text-sm rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
