import { useState, useMemo, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Shell from './components/layout/Shell.tsx';
import { DateRangeContext } from './hooks/useDateRange.ts';
import type { DateRange } from './hooks/useDateRange.ts';
import { useTheme } from './hooks/useTheme.ts';
import Skeleton from './components/ui/Skeleton.tsx';

const Overview = lazy(() => import('./pages/Overview.tsx'));
const SleepRecovery = lazy(() => import('./pages/SleepRecovery.tsx'));
const Training = lazy(() => import('./pages/Training.tsx'));
const Nutrition = lazy(() => import('./pages/Nutrition.tsx'));
const BodyComposition = lazy(() => import('./pages/BodyComposition.tsx'));
const Correlations = lazy(() => import('./pages/Correlations.tsx'));
const Alerts = lazy(() => import('./pages/Alerts.tsx'));
const Digest = lazy(() => import('./pages/Digest.tsx'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function PageFallback() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-3 gap-6">
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    </div>
  );
}

export default function App() {
  const { theme, toggle } = useTheme();
  const [range, setRange] = useState<DateRange>({ start: null, end: null });

  const dateCtx = useMemo(() => {
    const params: Record<string, string> = {};
    if (range.start) params.start = range.start;
    if (range.end) params.end = range.end;
    return { range, setRange, params };
  }, [range]);

  return (
    <QueryClientProvider client={queryClient}>
      <DateRangeContext.Provider value={dateCtx}>
        <BrowserRouter>
          <Shell theme={theme} onToggleTheme={toggle}>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/sleep" element={<SleepRecovery />} />
                <Route path="/training" element={<Training />} />
                <Route path="/nutrition" element={<Nutrition />} />
                <Route path="/body" element={<BodyComposition />} />
                <Route path="/correlations" element={<Correlations />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/digest" element={<Digest />} />
              </Routes>
            </Suspense>
          </Shell>
        </BrowserRouter>
      </DateRangeContext.Provider>
    </QueryClientProvider>
  );
}
