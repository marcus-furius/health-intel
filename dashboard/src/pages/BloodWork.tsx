import Header from '../components/layout/Header.tsx';
import MetricCard from '../components/ui/MetricCard.tsx';
import ChartCard from '../components/ui/ChartCard.tsx';
import TrendChart from '../components/charts/TrendChart.tsx';
import { useBloodwork } from '../hooks/queries.ts';
import { fmtNumber, fmtDateLong } from '../lib/format.ts';
import { chartColors } from '../lib/colors.ts';

export default function BloodWork() {
  const { data: bloodRes, isLoading } = useBloodwork();
  const tests = bloodRes?.data || [];
  const referenceRanges = bloodRes?.reference_ranges || {};
  
  const latest = tests.length ? tests[tests.length - 1] : null;
  const previous = tests.length >= 2 ? tests[tests.length - 2] : null;

  function getStatusColor(marker: string, value: number | null) {
    if (value == null) return '#A69F95';
    const range = referenceRanges[marker];
    if (!range) return '#A69F95';

    function inRange(v: number, r: number | number[] | number[][]): boolean {
      if (Array.isArray(r)) {
        if (Array.isArray(r[0])) {
          return (r as number[][]).some(sub => v >= sub[0] && v <= sub[1]);
        }
        return v >= r[0] && v <= r[1];
      }
      return false;
    }

    if (range.critical && inRange(value, range.critical)) return '#1A1A1A'; // Critical - Black
    if (range.red && inRange(value, range.red)) return chartColors.stress; // Red
    if (range.amber && inRange(value, range.amber)) return chartColors.warning; // Amber
    if (range.green && inRange(value, range.green)) return chartColors.recovery; // Green
    
    return '#A69F95';
  }

  function getTrend(marker: string) {
    if (!latest || !previous) return null;
    const currentVal = latest[marker] as number | null;
    const prevVal = previous[marker] as number | null;
    if (currentVal == null || prevVal == null) return null;
    return currentVal - prevVal;
  }

  const kpis = [
    { label: 'Testosterone', marker: 'testosterone_nmol', unit: 'nmol/l' },
    { label: 'Free Testosterone', marker: 'free_testosterone_nmol', unit: 'nmol/l' },
    { label: 'Oestradiol', marker: 'oestradiol_pmol', unit: 'pmol/l' },
    { label: 'Haematocrit', marker: 'haematocrit_pct', unit: '%' },
    { label: 'PSA', marker: 'psa_ug', unit: 'µg/l' },
    { label: 'HbA1c', marker: 'hba1c_mmol', unit: 'mmol/mol' },
    { label: 'HDL', marker: 'hdl_mmol', unit: 'mmol/l' },
  ];

  return (
    <div>
      <Header title="Blood Work" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 lg:gap-7 mb-6 animate-stagger">
        {kpis.slice(0, 4).map(kpi => (
          <MetricCard
            key={kpi.marker}
            label={kpi.label}
            value={latest?.[kpi.marker] as number}
            unit={kpi.unit}
            trend={getTrend(kpi.marker)}
            sparkline={[]}
            color={getStatusColor(kpi.marker, latest?.[kpi.marker] as number)}
            loading={isLoading}
          />
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-5 lg:gap-7 mb-10 animate-stagger delay-100">
        {kpis.slice(4).map(kpi => (
          <MetricCard
            key={kpi.marker}
            label={kpi.label}
            value={latest?.[kpi.marker] as number}
            unit={kpi.unit}
            trend={getTrend(kpi.marker)}
            sparkline={[]}
            color={getStatusColor(kpi.marker, latest?.[kpi.marker] as number)}
            loading={isLoading}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Hormone Panel" subtitle="Total & Free Testosterone">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'testosterone_nmol', color: chartColors.training, name: 'Total T (nmol/l)', type: 'line' },
              { dataKey: 'free_testosterone_nmol', color: chartColors.recovery, name: 'Free T (nmol/l)', type: 'line', yAxisId: 'right' }
            ]}
          />
        </ChartCard>
        <ChartCard title="TRT Safety Markers" subtitle="Haematocrit & Haemoglobin">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'haematocrit_pct', color: chartColors.stress, name: 'Haematocrit (%)', type: 'line' },
              { dataKey: 'haemoglobin_g', color: '#A69F95', name: 'Haemoglobin (g/l)', type: 'line', yAxisId: 'right' }
            ]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Lipid Panel" subtitle="Cholesterol markers">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'total_cholesterol_mmol', color: '#A69F95', name: 'Total Chol', type: 'line' },
              { dataKey: 'hdl_mmol', color: chartColors.recovery, name: 'HDL', type: 'line' },
              { dataKey: 'ldl_mmol', color: chartColors.stress, name: 'LDL', type: 'line' },
            ]}
          />
        </ChartCard>
        <ChartCard title="Liver Function" subtitle="Enzymes & Proteins">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'alt_u', color: chartColors.stress, name: 'ALT (U/l)', type: 'line' },
              { dataKey: 'alp_u', color: '#A69F95', name: 'ALP (U/l)', type: 'line' },
              { dataKey: 'ggt_u', color: chartColors.warning, name: 'GGT (U/l)', type: 'line' },
            ]}
          />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-7 mb-6">
        <ChartCard title="Kidney Function" subtitle="Creatinine, eGFR, Urea">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'creatinine_umol', color: chartColors.sleep, name: 'Creatinine', type: 'line' },
              { dataKey: 'egfr_ml', color: chartColors.recovery, name: 'eGFR', type: 'line', yAxisId: 'right' },
              { dataKey: 'urea_mmol', color: '#A69F95', name: 'Urea', type: 'line' },
            ]}
          />
        </ChartCard>
        <ChartCard title="Thyroid & Metabolism" subtitle="TSH & HbA1c">
          <TrendChart
            data={tests as Record<string, unknown>[]}
            series={[
              { dataKey: 'tsh_miu', color: chartColors.training, name: 'TSH (mIU/l)', type: 'line' },
              { dataKey: 'hba1c_mmol', color: chartColors.warning, name: 'HbA1c (mmol/mol)', type: 'line', yAxisId: 'right' },
            ]}
          />
        </ChartCard>
      </div>

      <ChartCard title="Full Results History" className="mt-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="text-left py-3 pr-4 text-text-muted font-medium">Marker</th>
                {tests.map(test => (
                  <th key={test.day as string} className="text-right py-3 px-4 text-text-muted font-medium min-w-[100px]">
                    {fmtDateLong(test.day as string)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { label: 'Total Testosterone (nmol/l)', key: 'testosterone_nmol' },
                { label: 'Free Testosterone (nmol/l)', key: 'free_testosterone_nmol' },
                { label: 'Oestradiol (pmol/l)', key: 'oestradiol_pmol' },
                { label: 'SHBG (nmol/l)', key: 'shbg_nmol' },
                { label: 'Prolactin (mIU/l)', key: 'prolactin_miu' },
                { label: 'PSA (µg/l)', key: 'psa_ug' },
                { label: 'Haematocrit (%)', key: 'haematocrit_pct' },
                { label: 'Haemoglobin (g/l)', key: 'haemoglobin_g' },
                { label: 'Red Blood Cells (10^12/L)', key: 'rbc_count' },
                { label: 'White Blood Cells (10^9/L)', key: 'wbc_count' },
                { label: 'Total Cholesterol (mmol/l)', key: 'total_cholesterol_mmol' },
                { label: 'HDL (mmol/l)', key: 'hdl_mmol' },
                { label: 'LDL (mmol/l)', key: 'ldl_mmol' },
                { label: 'ALT (U/l)', key: 'alt_u' },
                { label: 'eGFR (ml/min/1.73m²)', key: 'egfr_ml' },
                { label: 'TSH (mIU/l)', key: 'tsh_miu' },
                { label: 'HbA1c (mmol/mol)', key: 'hba1c_mmol' },
              ].map(marker => (
                <tr key={marker.key} className="border-b border-border-subtle/50 hover:bg-bg-elevated/30 transition-colors">
                  <td className="py-3 pr-4 text-text-primary font-medium">{marker.label}</td>
                  {tests.map(test => {
                    const val = test[marker.key] as number | null;
                    const color = getStatusColor(marker.key, val);
                    return (
                      <td key={test.day as string} className="text-right py-3 px-4 font-mono">
                        <span style={{ color: val != null ? color : undefined }}>
                          {val != null ? fmtNumber(val, 2) : '—'}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </div>
  );
}
