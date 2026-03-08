import Header from '../components/layout/Header.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import { useDigest } from '../hooks/queries.ts';
import { fmtNumber, fmtDateLong } from '../lib/format.ts';

export default function Digest() {
  const { data: digestRes, isLoading } = useDigest();

  const items = digestRes?.items || [];
  const wins = items.filter(i => i.delta != null && i.delta > 0);
  const losses = items.filter(i => i.delta != null && i.delta < 0);

  return (
    <div>
      <Header title="Weekly Digest" />

      {isLoading ? (
        <p className="text-text-muted">Loading digest...</p>
      ) : (
        <>
          <div className="flex gap-4 mb-6 text-sm text-text-muted">
            <span>Current week: {digestRes?.current_week ? fmtDateLong(digestRes.current_week) : '—'}</span>
            <span>vs Previous: {digestRes?.previous_week ? fmtDateLong(digestRes.previous_week) : '—'}</span>
          </div>

          {/* Summary table */}
          <ChartCard title="Week-over-Week" className="mb-8">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left py-3 pr-4 text-text-muted font-medium">Metric</th>
                    <th className="text-right py-3 px-4 text-text-muted font-medium">Last Week</th>
                    <th className="text-right py-3 px-4 text-text-muted font-medium">This Week</th>
                    <th className="text-right py-3 pl-4 text-text-muted font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <tr key={item.label} className="border-b border-border-subtle/50">
                      <td className="py-3 pr-4 text-text-primary font-medium">{item.label}</td>
                      <td className="text-right py-3 px-4 text-text-secondary">
                        {item.previous != null ? `${fmtNumber(item.previous, item.previous % 1 !== 0 ? 1 : 0)} ${item.unit}` : '—'}
                      </td>
                      <td className="text-right py-3 px-4 text-text-primary font-medium">
                        {item.current != null ? `${fmtNumber(item.current, item.current % 1 !== 0 ? 1 : 0)} ${item.unit}` : '—'}
                      </td>
                      <td className={`text-right py-3 pl-4 font-medium ${
                        item.delta == null ? 'text-text-muted'
                          : item.delta > 0 ? 'text-chart-emerald'
                          : item.delta < 0 ? 'text-chart-rose'
                          : 'text-text-muted'
                      }`}>
                        {item.delta != null ? `${item.delta > 0 ? '+' : ''}${fmtNumber(item.delta, Math.abs(item.delta) % 1 !== 0 ? 1 : 0)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>

          {/* Wins & Losses */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
            <ChartCard title="Wins" subtitle="Improved vs last week">
              {wins.length > 0 ? (
                <div className="space-y-3">
                  {wins.map(w => (
                    <div key={w.label} className="flex items-center justify-between">
                      <span className="text-text-primary">{w.label}</span>
                      <span className="text-chart-emerald font-medium">
                        +{fmtNumber(w.delta!, Math.abs(w.delta!) % 1 !== 0 ? 1 : 0)} {w.unit}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">No improvements this week</p>
              )}
            </ChartCard>
            <ChartCard title="Needs Attention" subtitle="Declined vs last week">
              {losses.length > 0 ? (
                <div className="space-y-3">
                  {losses.map(l => (
                    <div key={l.label} className="flex items-center justify-between">
                      <span className="text-text-primary">{l.label}</span>
                      <span className="text-chart-rose font-medium">
                        {fmtNumber(l.delta!, Math.abs(l.delta!) % 1 !== 0 ? 1 : 0)} {l.unit}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted">No declines this week</p>
              )}
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}
