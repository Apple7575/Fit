import { formatAmount } from './formatAmount';

interface KeyMetricCardProps {
  label: string;
  value: number | null;
}

export function KeyMetricCard({ label, value }: KeyMetricCardProps) {
  const isMissing = value === null;

  return (
    <article
      aria-label={label}
      className="min-h-32 rounded-2xl border border-slate-200 bg-slate-50 p-5"
    >
      <p className="text-sm font-bold text-slate-600">{label}</p>
      {isMissing ? (
        <p className="mt-4 text-lg font-semibold text-slate-400">미제공</p>
      ) : (
        <p className="mt-4 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold tracking-tight text-slate-950">
            {formatAmount(value)}
          </span>
          <span className="text-sm font-semibold text-slate-500">원</span>
        </p>
      )}
    </article>
  );
}
