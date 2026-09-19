import { KEY_METRIC_KEYS, METRIC_LABELS, type KeyMetricsData } from '../../types/metrics';
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

/**
 * 기준연도 핵심지표. 값이 있는 지표만 카드로 보여주고, 없는 지표는 카드 여섯 장 중 절반이
 * "미제공"으로 남지 않도록 한 줄로 접는다 (0 으로 위장하지 않는다).
 */
export function GrowthKpiRow({ data }: GrowthKpiRowProps) {
  const byKey = new Map(data.metrics.map((m) => [m.key, m]));
  const available = KEY_METRIC_KEYS.filter((key) => (byKey.get(key)?.value ?? null) !== null);
  const missing = KEY_METRIC_KEYS.filter((key) => (byKey.get(key)?.value ?? null) === null);
  const yearLabel = data.year !== null ? `${data.year}년` : '기준연도';

  return (
    <div className="space-y-2">
      <ul
        aria-label="기준연도 핵심지표"
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"
      >
        {available.map((key) => {
          const value = byKey.get(key)!.value as number;
          return (
            <li
              aria-label={METRIC_LABELS[key]}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
              key={key}
            >
              <p className="text-xs font-semibold text-slate-400">{yearLabel}</p>
              <p className="mt-2 flex items-baseline gap-1">
                <span className="text-2xl font-extrabold tracking-tight text-slate-950">
                  {formatMetricCompactValue(key, value)}
                </span>
                <span className="text-sm font-semibold text-slate-500">{metricUnitLabel(key)}</span>
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-600">{KPI_LABELS[key]}</p>
            </li>
          );
        })}
        {available.length === 0 && (
          <li className="col-span-full rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm font-semibold text-slate-400">
            {yearLabel} 핵심지표가 미제공입니다
          </li>
        )}
      </ul>
      {missing.length > 0 && available.length > 0 && (
        <p className="text-xs text-slate-400">
          {missing.map((key) => KPI_LABELS[key]).join(' · ')} 은(는) 이 기업의 공시 데이터가 없어
          표시하지 않습니다.
        </p>
      )}
    </div>
  );
}
