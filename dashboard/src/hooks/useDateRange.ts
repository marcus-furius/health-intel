import { createContext, useContext } from 'react';

export interface DateRange {
  start: string | null;
  end: string | null;
}

export interface DateRangeCtx {
  range: DateRange;
  setRange: (r: DateRange) => void;
  params: Record<string, string>;
}

export const DateRangeContext = createContext<DateRangeCtx>({
  range: { start: null, end: null },
  setRange: () => {},
  params: {},
});

export function useDateRange() {
  return useContext(DateRangeContext);
}
