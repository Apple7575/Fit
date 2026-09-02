import { KEY_METRIC_KEYS, type KeyMetric } from '../../types/metrics';
import { KeyMetricCard } from './KeyMetricCard';

interface KeyMetricsGridProps {
  metrics: KeyMetric[];
}

/** 핵심지표 6종을 고정 순서로 그린다. 응답에 없는 키는 미제공 처리. */
export function KeyMetricsGrid({ metrics }: KeyMetricsGridProps) {
  const byKey = new Map(metrics.map((m) => [m.key, m]));

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {KEY_METRIC_KEYS.map((key) => {
        const metric = byKey.get(key);
        return (
          <KeyMetricCard
            changeRate={metric?.changeRate ?? null}
            key={key}
            metricKey={key}
            value={metric?.value ?? null}
          />
        );
      })}
    </div>
  );
}
