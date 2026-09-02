import { UNIT_LABELS } from '../../types/metrics';
import { formatMetricNumber } from '../../utils/formatMetric';
import {
  COMPARISON_METRIC_KEYS,
  COMPARISON_METRIC_LABELS,
  COMPARISON_METRIC_UNITS,
  type ComparisonCompany,
} from './types';

interface ComparisonTableProps {
  companies: ComparisonCompany[];
}

/**
 * 기업 × 비교 지표 10종 전체 표. 조회 기업 행은 맨 위·강조.
 * 값 없음은 "미제공"(0 아님), 음수는 손실 색.
 */
export function ComparisonTable({ companies }: ComparisonTableProps) {
  const ordered = [...companies].sort(
    (a, b) => Number(b.isTarget) - Number(a.isTarget),
  );

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="min-w-full text-sm">
        <caption className="sr-only">기업별 비교 지표 전체 표</caption>
        <thead className="bg-slate-50 text-left text-xs font-bold text-slate-500">
          <tr>
            <th className="sticky left-0 bg-slate-50 px-4 py-3" scope="col">
              기업
            </th>
            {COMPARISON_METRIC_KEYS.map((key) => (
              <th className="px-4 py-3 whitespace-nowrap" key={key} scope="col">
                {COMPARISON_METRIC_LABELS[key]}
                <span className="ml-1 font-medium text-slate-400">
                  ({UNIT_LABELS[COMPARISON_METRIC_UNITS[key]]})
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map((company) => (
            <tr
              className={
                company.isTarget
                  ? 'bg-blue-50/60 font-semibold text-blue-900'
                  : 'text-slate-700'
              }
              key={company.corpCode}
            >
              <th
                className={`sticky left-0 px-4 py-3 text-left whitespace-nowrap ${
                  company.isTarget ? 'bg-blue-50' : 'bg-white'
                }`}
                scope="row"
              >
                {company.corpName}
                {company.isTarget && (
                  <span className="ml-2 rounded-full bg-blue-600 px-2 py-0.5 text-[11px] font-bold text-white">
                    조회 기업
                  </span>
                )}
              </th>
              {COMPARISON_METRIC_KEYS.map((key) => {
                const value = company.values[key] ?? null;
                return (
                  <td
                    className={`px-4 py-3 whitespace-nowrap tabular-nums ${
                      value === null
                        ? 'text-slate-400'
                        : value < 0
                          ? 'text-rose-600'
                          : ''
                    }`}
                    key={key}
                  >
                    {value === null
                      ? '미제공'
                      : formatMetricNumber(COMPARISON_METRIC_UNITS[key], value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
