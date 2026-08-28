import { KeyMetricCard } from './KeyMetricCard';
import { METRIC_KEYS, METRIC_LABELS, type KeyMetric } from './types';

interface KeyMetricsSectionProps {
  metrics: KeyMetric[];
  year: number;
}

export function KeyMetricsSection({ metrics, year }: KeyMetricsSectionProps) {
  const valueByKey = new Map(metrics.map((m) => [m.key, m.value]));

  return (
    <section
      aria-labelledby="key-metrics-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="mb-6">
        <h2
          className="text-xl font-extrabold text-slate-950 sm:text-2xl"
          id="key-metrics-title"
        >
          {year}년 핵심지표
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          {year}년 연결재무제표 기준 · 단위: 원
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {METRIC_KEYS.map((key) => (
          <KeyMetricCard
            key={key}
            label={METRIC_LABELS[key]}
            value={valueByKey.get(key) ?? null}
          />
        ))}
      </div>
    </section>
  );
}
