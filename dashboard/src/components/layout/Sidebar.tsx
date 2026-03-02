import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Moon,
  Bed,
  Dumbbell,
  Apple,
  Scale,
  GitCompareArrows,
  AlertTriangle,
  Sun,
  Heart,
} from 'lucide-react';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/sleep', icon: Bed, label: 'Sleep & Recovery' },
  { to: '/training', icon: Dumbbell, label: 'Training' },
  { to: '/nutrition', icon: Apple, label: 'Nutrition' },
  { to: '/body', icon: Scale, label: 'Body Composition' },
  { to: '/correlations', icon: GitCompareArrows, label: 'Correlations' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
];

interface Props {
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export default function Sidebar({ theme, onToggleTheme }: Props) {
  return (
    <aside className="no-print fixed left-0 top-0 bottom-0 w-60 bg-bg-card border-r border-border-subtle flex flex-col z-20">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-border-subtle">
        <Heart className="w-6 h-6 text-chart-rose" />
        <span className="text-lg font-semibold tracking-tight">Health Intel</span>
      </div>
      <nav className="flex-1 py-3 px-3 space-y-0.5 overflow-y-auto">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
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
      <div className="px-3 pb-4">
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
