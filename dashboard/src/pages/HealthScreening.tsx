import { useState } from 'react';
import { ChevronDown, ChevronUp, ArrowUpRight, ArrowDownRight, ArrowRight, Plus } from 'lucide-react';
import Header from '../components/layout/Header.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import AlertCard from '../components/ui/AlertCard.tsx';
import Skeleton from '../components/ui/Skeleton.tsx';
import GaugeChart from '../components/charts/GaugeChart.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import { useHealthScreening, useAddVo2Max } from '../hooks/queries.ts';
import { domainColors, severityColors, colors } from '../lib/colors.ts';
import { fmtDate } from '../lib/format.ts';
import type { DomainScore } from '../lib/api.ts';

const trendIcons: Record<string, typeof ArrowUpRight> = {
  improving: ArrowUpRight,
  declining: ArrowDownRight,
  stable: ArrowRight,
};

const trendLabels: Record<string, string> = {
  improving: 'Improving',
  declining: 'Declining',
  stable: 'Stable',
};

const trendColors: Record<string, string> = {
  improving: 'text-chart-sage',
  declining: 'text-chart-rose',
  stable: 'text-text-muted',
};

function DomainCard({ domain }: { domain: DomainScore }) {
  const [expanded, setExpanded] = useState(false);
  const TrendIcon = trendIcons[domain.trend] || ArrowRight;
  const color = domainColors[domain.name] || colors.gold;

  if (!domain.available) {
    return (
      <div className="bg-bg-card border border-border-subtle rounded-2xl p-6 opacity-50">
        <div className="flex items-center gap-4">
          <div className="relative">
            <GaugeChart score={0} size={80} showScore={false} />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs text-text-muted">N/A</span>
            </div>
          </div>
          <div>
            <h3 className="font-serif text-text-primary text-sm">{domain.label}</h3>
            <p className="text-xs text-text-muted mt-1">No data available</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="bg-bg-card border border-border-subtle rounded-2xl p-6 transition-all hover:border-border-default hover:shadow-lg cursor-pointer"
      style={{ borderTopWidth: 3, borderTopColor: color }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-4">
        <div className="relative">
          <GaugeChart score={domain.score} size={80} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-text-primary text-sm">{domain.label}</h3>
          <div className="flex items-center gap-1.5 mt-1">
            <TrendIcon className={`w-3.5 h-3.5 ${trendColors[domain.trend]}`} />
            <span className={`text-xs ${trendColors[domain.trend]}`}>
              {trendLabels[domain.trend]}
            </span>
          </div>
          {domain.key_metric && (
            <p className="text-xs text-text-muted mt-1 truncate">{domain.key_metric}</p>
          )}
        </div>
        <div className="shrink-0">
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-text-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-muted" />
          )}
        </div>
      </div>
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border-subtle space-y-2">
          {domain.components.map((comp) => (
            <div key={comp.name} className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{comp.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-text-muted text-xs">{comp.detail}</span>
                <span className="font-medium text-text-primary w-10 text-right">
                  {Math.round(comp.score)}
                </span>
                <div className="w-16 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${comp.score}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Vo2MaxForm() {
  const mutation = useAddVo2Max();
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [value, setValue] = useState('');
  const [method, setMethod] = useState('manual');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const numValue = parseFloat(value);
    if (isNaN(numValue) || numValue <= 0) return;
    mutation.mutate({ date, value: numValue, method }, {
      onSuccess: () => setValue(''),
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-xs text-text-muted block mb-1">Date</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-full bg-bg-elevated border border-border-subtle rounded-xl px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-gold"
        />
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">VO2 Max (ml/kg/min)</label>
        <input
          type="number"
          step="0.1"
          min="10"
          max="90"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. 46"
          className="w-full bg-bg-elevated border border-border-subtle rounded-xl px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-gold"
        />
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">Method</label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="w-full bg-bg-elevated border border-border-subtle rounded-xl px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent-gold"
        >
          <option value="manual">Manual entry</option>
          <option value="lab_test">Lab test</option>
          <option value="watch_estimate">Watch estimate</option>
          <option value="field_test">Field test</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={mutation.isPending || !value}
        className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-accent-gold text-white rounded-xl text-sm font-medium hover:bg-[#D4B87D] transition-colors disabled:opacity-50"
      >
        <Plus className="w-4 h-4" />
        {mutation.isPending ? 'Saving…' : 'Add Entry'}
      </button>
      {mutation.isError && (
        <p className="text-xs text-chart-rose">Failed to save. Please try again.</p>
      )}
    </form>
  );
}

function scoreLabel(score: number): string {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Fair';
  if (score >= 40) return 'Needs Attention';
  return 'Poor';
}

export default function HealthScreening() {
  const { data, isLoading } = useHealthScreening();

  if (isLoading || !data) {
    return (
      <div>
        <Header title="Health Screening" />
        <div className="space-y-6">
          <Skeleton className="h-56 w-full rounded-2xl" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            {[...Array(7)].map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const vo2maxChartData = data.vo2max_history.map((e) => ({
    date: e.date,
    vo2max: e.value,
  }));

  const OverallTrendIcon = trendIcons[data.overall_trend] || ArrowRight;

  return (
    <div>
      <Header title="Health Screening" />

      {/* Overall Score */}
      <div className="flex flex-col items-center mb-10">
        <div className="bg-bg-card border border-border-subtle rounded-2xl p-8 flex flex-col items-center gap-4 animate-card-enter w-full max-w-md">
          <div className="relative">
            <GaugeChart score={data.overall_score} size={200} />
          </div>
          <div className="text-center">
            <p className="text-lg font-serif text-text-primary">
              {scoreLabel(data.overall_score)}
            </p>
            <div className="flex items-center justify-center gap-2 mt-2">
              <OverallTrendIcon className={`w-4 h-4 ${trendColors[data.overall_trend]}`} />
              <span className={`text-sm ${trendColors[data.overall_trend]}`}>
                {trendLabels[data.overall_trend]}
              </span>
              <span className="text-xs text-text-muted ml-2">
                {Math.round(data.data_completeness * 100)}% data coverage
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Domain Score Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 lg:gap-7 mb-10 animate-stagger">
        {data.domains.map((domain) => (
          <DomainCard key={domain.name} domain={domain} />
        ))}
      </div>

      {/* VO2 Max Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-10">
        <ChartCard
          title="VO2 Max History"
          subtitle={
            data.vo2max
              ? `Latest: ${data.vo2max.value} ml/kg/min — ${data.vo2max.category}`
              : 'No entries yet'
          }
        >
          {vo2maxChartData.length > 0 ? (
            <TrendChart
              data={vo2maxChartData}
              series={[{ dataKey: 'vo2max', color: colors.rose, name: 'VO2 Max' }]}
              xKey="date"
              height={220}
              referenceLine={{ y: 43.4, label: 'Excellent', color: colors.sage }}
            />
          ) : (
            <p className="text-sm text-text-muted py-8 text-center">
              Add your first VO2 Max entry to see the trend.
            </p>
          )}
        </ChartCard>

        <ChartCard title="Log VO2 Max" subtitle="Manual entry from test results">
          <Vo2MaxForm />
          {data.vo2max && (
            <div className="mt-4 pt-4 border-t border-border-subtle">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">Classification</span>
                <span
                  className="font-medium px-2.5 py-0.5 rounded-full text-xs"
                  style={{
                    backgroundColor: `${domainColors.cardiovascular}20`,
                    color: domainColors.cardiovascular,
                  }}
                >
                  {data.vo2max.category}
                </span>
              </div>
              <p className="text-xs text-text-muted mt-2">
                Based on male age 50-59 normative data. Superior ≥43.4, Excellent 39.2-43.3, Good 35.2-39.1, Fair 31.1-35.1, Poor ≤31.0 ml/kg/min.
              </p>
            </div>
          )}
        </ChartCard>
      </div>

      {/* Interventions */}
      {data.interventions.length > 0 && (
        <ChartCard title="Prioritised Interventions" subtitle="Based on lowest-scoring domains" className="mb-10">
          <div className="space-y-3">
            {data.interventions.map((interv, idx) => (
              <div
                key={idx}
                className="flex items-start gap-4 p-4 bg-bg-elevated rounded-xl"
              >
                <span
                  className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
                  style={{
                    backgroundColor:
                      interv.priority >= 4
                        ? severityColors.high
                        : interv.priority >= 3
                        ? severityColors.medium
                        : severityColors.low,
                  }}
                >
                  {interv.priority}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                      {interv.domain}
                    </span>
                  </div>
                  <p className="text-sm text-text-primary">{interv.action}</p>
                  <p className="text-xs text-text-muted mt-1">{interv.expected_impact}</p>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      )}

      {/* Risk Factors */}
      {data.risk_factors.length > 0 && (
        <div className="mb-10">
          <h2 className="text-xl font-serif mb-5">Risk Factors</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.risk_factors.slice(0, 10).map((alert, idx) => (
              <AlertCard key={idx} alert={alert} />
            ))}
          </div>
          {data.risk_factors.length > 10 && (
            <p className="text-sm text-text-muted mt-3 text-center">
              +{data.risk_factors.length - 10} more — view all on the Alerts page
            </p>
          )}
        </div>
      )}
    </div>
  );
}
