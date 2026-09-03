import {
  KEY_METRIC_KEYS,
  METRIC_LABELS,
  type KeyMetricsData,
} from '../../types/metrics';
import { formatMetricCompactValue, metricUnitLabel } from '../../utils/formatMetric';

interface GrowthKpiRowProps {
  data: KeyMetricsData;
}

const KPI_LABELS: Record<(typeof KEY_METRIC_KEYS)[number], string> = {
  revenue: '매출액',
  operating_profit: '영업이익',
  net_income: '당기순이익',
  employee_count: '직원 수',
  average_salary: '평균 급여',
  average_tenure: '평균 근속연수',
};

/** 기준연도 핵심지표 6장. 값 없으면 미제공(0 아님). */
export function GrowthKpiRow({ data }: GrowthKpiRowProps) {
  const byKey = new Map(data.metrics.map((m) => [m.key, m]));

  return (
    <ul
      aria-label="기준연도 핵심지표"
      className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"
    >
      {KEY_METRIC_KEYS.map((key) => {
        const metric = byKey.get(key);
        const value = metric?.value ?? null;
        return (
          <li
            aria-label={METRIC_LABELS[key]}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
            key={key}
          >
            <p className="text-xs font-semibold text-slate-400">
              {data.year !== null ? `${data.year}년` : '기준연도'}
            </p>
            <p className="mt-2 flex items-baseline gap-1">
              {value === null ? (
                <span className="text-lg font-semibold text-slate-400">미제공</span>
              ) : (
                <>
                  <span className="text-2xl font-extrabold tracking-tight text-slate-950">
                    {formatMetricCompactValue(key, value)}
                  </span>
                  <span className="text-sm font-semibold text-slate-500">
                    {metricUnitLabel(key)}
                  </span>
                </>
              )}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-600">{KPI_LABELS[key]}</p>
          </li>
        );
      })}
    </ul>
  );
}
