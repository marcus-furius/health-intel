import { useDateRange } from '../../hooks/useDateRange.ts';
import DateRangePicker from '../ui/DateRangePicker.tsx';
import PrintExport from '../ui/PrintExport.tsx';

interface Props {
  title: string;
}

export default function Header({ title }: Props) {
  const { range, setRange } = useDateRange();

  return (
    <header className="no-print flex items-center justify-between mb-8">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <div className="flex items-center gap-3">
        <DateRangePicker value={range} onChange={setRange} />
        <PrintExport />
      </div>
    </header>
  );
}
