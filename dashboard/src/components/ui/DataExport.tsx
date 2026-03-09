import { useState, useRef, useEffect } from 'react';
import { Download, ChevronDown, FileJson, FileSpreadsheet, FileCode, FileText } from 'lucide-react';

interface Props {
  data: Record<string, unknown>[];
  filename: string;
  labels?: Record<string, string>;
}

export default function DataExport({ data, filename, labels }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getExportData = () => {
    if (!labels) return data;
    return data.map(row => {
      const newRow: Record<string, unknown> = {};
      Object.entries(row).forEach(([key, value]) => {
        const label = labels[key] || key;
        newRow[label] = value;
      });
      return newRow;
    });
  };

  const downloadFile = (content: string, type: string, extension: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.${extension}`;
    a.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const exportCSV = () => {
    const exportData = getExportData();
    if (!exportData.length) return;
    const keys = Object.keys(exportData[0]);
    const csv = [
      keys.join(','),
      ...exportData.map(row => keys.map(k => {
        const v = row[k];
        if (v == null) return '';
        const s = String(v);
        return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(','))
    ].join('\n');
    downloadFile(csv, 'text/csv', 'csv');
  };

  const exportJSON = () => {
    downloadFile(JSON.stringify(data, null, 2), 'application/json', 'json');
  };

  const exportXML = () => {
    const exportData = getExportData();
    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<root>\n';
    exportData.forEach(row => {
      xml += '  <item>\n';
      Object.entries(row).forEach(([key, val]) => {
        const cleanKey = key.replace(/[^a-zA-Z0-9]/g, '_').replace(/^(\d)/, '_$1');
        xml += `    <${cleanKey}>${val ?? ''}</${cleanKey}>\n`;
      });
      xml += '  </item>\n';
    });
    xml += '</root>';
    downloadFile(xml, 'application/xml', 'xml');
  };

  const exportTXT = () => {
    const exportData = getExportData();
    if (!exportData.length) return;
    const keys = Object.keys(exportData[0]);
    const txt = exportData.map(row => 
      keys.map(k => `${k}: ${row[k] ?? '—'}`).join('\n')
    ).join('\n\n---\n\n');
    downloadFile(txt, 'text/plain', 'txt');
  };

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm bg-bg-elevated border border-border-subtle rounded-xl text-text-secondary hover:text-text-primary hover:border-border-default transition-colors no-print"
      >
        <Download className="w-4 h-4" />
        <span>Export</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 origin-top-right rounded-xl bg-bg-card border border-border-subtle shadow-xl shadow-[#0F0E0D]/20 z-50 overflow-hidden animate-in fade-in zoom-in duration-100">
          <div className="py-1">
            <button
              onClick={exportCSV}
              className="flex items-center w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors gap-3"
            >
              <FileSpreadsheet className="w-4 h-4 text-[#50B88E]" />
              Excel / CSV
            </button>
            <button
              onClick={exportJSON}
              className="flex items-center w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors gap-3"
            >
              <FileJson className="w-4 h-4 text-[#7A6FBE]" />
              JSON
            </button>
            <button
              onClick={exportXML}
              className="flex items-center w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors gap-3"
            >
              <FileCode className="w-4 h-4 text-[#E8915A]" />
              XML
            </button>
            <button
              onClick={exportTXT}
              className="flex items-center w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors gap-3"
            >
              <FileText className="w-4 h-4 text-[#A69F95]" />
              Plain Text
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
