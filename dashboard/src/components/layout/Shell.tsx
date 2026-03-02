import type { ReactNode } from 'react';
import Sidebar from './Sidebar.tsx';

interface Props {
  children: ReactNode;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export default function Shell({ children, theme, onToggleTheme }: Props) {
  return (
    <div className="min-h-screen">
      <Sidebar theme={theme} onToggleTheme={onToggleTheme} />
      <main className="ml-60 p-8 max-w-[1400px]">
        {children}
      </main>
    </div>
  );
}
