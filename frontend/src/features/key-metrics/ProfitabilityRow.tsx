import { PROFITABILITY_LABELS, type Profitability } from '../../types/metrics';

interface ProfitabilityRowProps {
  profitability: Profitability;
}

const ORDER: Array<keyof Profitability> = ['operatingMargin', 'netMargin', 'debtRatio'];

/** 소수점 1자리 %, 불필요한 .0 은 뗀다 */
const formatRatio = (v: number) =>
  `${Number.isInteger(v) ? v.toLocaleString('ko-KR') : v.toFixed(1)}%`;

/** 수익성·안정성 비율 3종. 값 없는 항목은 미제공. */
export function ProfitabilityRow({ profitability }: ProfitabilityRowProps) {
  return (
    <div
      aria-label="수익성·안정성 비율"
      className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      role="group"
    >
      {ORDER.map((field) => {
        const value = profitability[field];
        const label = PROFITABILITY_LABELS[field];
        return (
          <article
            aria-label={label}
            className="rounded-2xl border border-slate-200 bg-white p-5"
            key={field}
          >
            <p className="text-sm font-bold text-slate-600">{label}</p>
            {value === null ? (
              <p className="mt-3 text-lg font-semibold text-slate-400">미제공</p>
            ) : (
              <p className="mt-3 text-2xl font-extrabold tracking-tight text-slate-950">
                {formatRatio(value)}
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
