import { useDateRange } from '../../hooks/useDateRange.ts';
import DateRangePicker from '../ui/DateRangePicker.tsx';
import PrintExport from '../ui/PrintExport.tsx';

interface Props {
  title: string;
}

export default function Header({ title }: Props) {
  const { range, setRange } = useDateRange();

  const today = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });

  return (
    <>
      <div className="print-header">
        <h1>{title} — Health Intel</h1>
        <span>Generated {today}</span>
      </div>
      <header className="no-print flex items-center justify-between mb-10">
        <h1 className="text-3xl font-serif tracking-tight">{title}</h1>
        <div className="flex items-center gap-3">
          <DateRangePicker value={range} onChange={setRange} />
          <PrintExport />
        </div>
      </header>
    </>
  );
}
