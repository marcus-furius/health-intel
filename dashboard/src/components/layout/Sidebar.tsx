import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  LayoutDashboard,
  Moon,
  Bed,
  Dumbbell,
  Apple,
  Scale,
  GitCompareArrows,
  AlertTriangle,
  CalendarDays,
  Sun,
  Heart,
  RefreshCw,
  X,
} from 'lucide-react';
import { apiReload } from '../../lib/api.ts';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/sleep', icon: Bed, label: 'Sleep & Recovery' },
  { to: '/training', icon: Dumbbell, label: 'Training' },
  { to: '/nutrition', icon: Apple, label: 'Nutrition' },
  { to: '/body', icon: Scale, label: 'Body Composition' },
  { to: '/correlations', icon: GitCompareArrows, label: 'Correlations' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { to: '/digest', icon: CalendarDays, label: 'Weekly Digest' },
];

interface Props {
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  mobileOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ theme, onToggleTheme, mobileOpen, onClose }: Props) {
  const queryClient = useQueryClient();
  const [reloading, setReloading] = useState(false);

  async function handleReload() {
    setReloading(true);
    try {
      await apiReload();
      await queryClient.invalidateQueries();
    } finally {
      setReloading(false);
    }
  }

  return (
    <aside className={`no-print fixed left-0 top-0 bottom-0 w-60 bg-bg-card border-r border-border-subtle flex flex-col z-40 transition-transform duration-200 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
      <div className="flex items-center justify-between px-5 py-5 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <Heart className="w-6 h-6 text-chart-rose" />
          <span className="text-lg font-semibold tracking-tight">Health Intel</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="lg:hidden text-text-secondary hover:text-text-primary">
            <X className="w-5 h-5" />
          </button>
        )}
      </div>
      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-bg-elevated text-text-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated/50'
              }`
            }
          >
            <Icon className="w-[18px] h-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-3 pb-4 space-y-0.5">
        <button
          onClick={handleReload}
          disabled={reloading}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated/50 transition-colors w-full disabled:opacity-50"
        >
          <RefreshCw className={`w-[18px] h-[18px] ${reloading ? 'animate-spin' : ''}`} />
          {reloading ? 'Reloading…' : 'Reload data'}
        </button>
        <button
          onClick={onToggleTheme}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated/50 transition-colors w-full"
        >
          {theme === 'dark' ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  );
}
