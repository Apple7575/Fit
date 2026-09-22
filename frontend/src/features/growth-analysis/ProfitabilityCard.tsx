import { PROFITABILITY_LABELS, type Profitability } from '../../types/metrics';

interface ProfitabilityCardProps {
  year: number | null;
  profitability: Profitability;
}

const ORDER: Array<keyof Profitability> = ['operatingMargin', 'netMargin', 'debtRatio'];

const formatRatio = (v: number) =>
  `${Number.isInteger(v) ? v.toLocaleString('ko-KR') : v.toFixed(1)}%`;

/** 수익성·안정성 비율 3종. 값 없는 항목은 미제공. 업계 상위 같은 판정은 근거 데이터가 없어 넣지 않는다. */
export function ProfitabilityCard({ year, profitability }: ProfitabilityCardProps) {
  return (
    <section
      aria-labelledby="profitability-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <h3 className="text-lg font-extrabold text-slate-950" id="profitability-title">
        수익성 / 안정성{' '}
        {year !== null && (
          <span className="text-sm font-semibold text-slate-400">({year}년)</span>
        )}
      </h3>
      <dl
        aria-label="수익성·안정성 비율"
        className="mt-4 grid grid-cols-3 divide-x divide-slate-100 rounded-2xl border border-slate-200"
      >
        {ORDER.map((field) => {
          const value = profitability[field];
          return (
            <div className="px-3 py-4 text-center" key={field}>
              <dt className="text-xs font-bold text-slate-500">
                {PROFITABILITY_LABELS[field]}
              </dt>
              <dd
                className={`mt-2 text-xl font-extrabold tabular-nums ${
                  value === null ? 'text-slate-400' : 'text-slate-950'
                }`}
              >
                {value === null ? '미제공' : formatRatio(value)}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
