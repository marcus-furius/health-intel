import { useState } from 'react';
import type { ReactNode } from 'react';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar.tsx';

interface Props {
  children: ReactNode;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export default function Shell({ children, theme, onToggleTheme }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Mobile hamburger */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-bg-card border-b border-border-subtle flex items-center px-4 z-30 no-print">
        <button onClick={() => setSidebarOpen(true)} className="text-text-secondary hover:text-text-primary">
          <Menu className="w-6 h-6" />
        </button>
        <span className="ml-3 text-lg font-semibold tracking-tight">Health Intel</span>
      </div>

      {/* Overlay backdrop */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 z-30 no-print" onClick={() => setSidebarOpen(false)} />
      )}

      <Sidebar theme={theme} onToggleTheme={onToggleTheme} mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="ml-0 lg:ml-60 p-4 pt-18 lg:pt-8 lg:p-8 max-w-[1400px]">
        {children}
      </main>
    </div>
  );
}
