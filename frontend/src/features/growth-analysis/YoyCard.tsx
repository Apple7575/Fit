import type { KeyMetric, MetricKey } from '../../types/metrics';
import { formatChangeRate } from '../../utils/formatChangeRate';
import { formatDelta } from '../../utils/formatDelta';

interface YoyCardProps {
  year: number | null;
  metrics: KeyMetric[];
}

const ROWS: Array<{ key: MetricKey; label: string }> = [
  { key: 'revenue', label: '매출 증가율' },
  { key: 'operating_profit', label: '영업이익 증가율' },
  { key: 'employee_count', label: '직원 증가율' },
  { key: 'average_salary', label: '평균 급여 증가율' },
];

/** 전년 대비 증가율 4종. 전년 값이 없으면 미제공(추정하지 않음). */
export function YoyCard({ year, metrics }: YoyCardProps) {
  const byKey = new Map(metrics.map((m) => [m.key, m]));
  const range = year !== null ? `${year - 1} → ${year}` : '전년 → 기준연도';

  return (
    <section
      aria-labelledby="yoy-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <h3 className="text-lg font-extrabold text-slate-950" id="yoy-title">
        전년 대비{' '}
        <span className="text-sm font-semibold text-slate-400">({range})</span>
      </h3>
      <ul className="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-200">
        {ROWS.map(({ key, label }) => {
          const m = byKey.get(key);
          const rate = m?.changeRate ?? null;
          const hasDelta = m?.value != null && m?.prevValue != null;
          const tone =
            rate === null
              ? 'text-slate-400'
              : rate > 0
                ? 'text-emerald-700'
                : rate < 0
                  ? 'text-rose-700'
                  : 'text-slate-700';
          return (
            <li
              aria-label={label}
              className="flex items-center justify-between gap-4 px-4 py-3.5"
              key={key}
            >
              <span className="text-sm font-semibold text-slate-700">{label}</span>
              <span className="text-right">
                <span className={`block text-base font-extrabold tabular-nums ${tone}`}>
                  {rate === null ? (
                    '미제공'
                  ) : (
                    <>
                      {formatChangeRate(rate)}
                      <span aria-hidden="true" className="ml-1 text-xs">
                        {rate > 0 ? '▲' : rate < 0 ? '▼' : '─'}
                      </span>
                    </>
                  )}
                </span>
                {hasDelta && m && (
                  <span className="block text-xs font-medium text-slate-500">
                    {formatDelta(key, m.value as number, m.prevValue as number)}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
