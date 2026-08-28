import { KeyMetricCard } from './KeyMetricCard';
import { METRIC_KEYS, METRIC_LABELS, type KeyMetric } from '../../types/metrics';

interface KeyMetricsGridProps {
  metrics: KeyMetric[];
}

/** 6개 지표를 고정 순서로 그린다. 응답에 없는 키는 미제공 처리. */
export function KeyMetricsGrid({ metrics }: KeyMetricsGridProps) {
  const valueByKey = new Map(metrics.map((m) => [m.key, m.value]));

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {METRIC_KEYS.map((key) => (
        <KeyMetricCard
          key={key}
          label={METRIC_LABELS[key]}
          value={valueByKey.get(key) ?? null}
        />
      ))}
    </div>
  );
}
