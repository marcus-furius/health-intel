import { Printer } from 'lucide-react';

export default function PrintExport() {
  return (
    <button
      onClick={() => window.print()}
      className="flex items-center gap-2 px-3 py-2 text-sm bg-bg-elevated border border-border-subtle rounded-xl text-text-secondary hover:text-text-primary hover:border-border-default transition-colors"
      title="Print / Export PDF"
    >
      <Printer className="w-4 h-4" />
    </button>
  );
}
