import { METRIC_UNITS, UNIT_LABELS, type MetricKey } from '../types/metrics';
import { formatMetricCompact } from './formatMetric';

/** 증감액: 부호 + 짧은 단위 표기 (+5.1조 원 / +3,100명 / +501만 원) */
export function formatDelta(key: MetricKey, value: number, prevValue: number): string {
  const delta = value - prevValue;
  const unit = METRIC_UNITS[key];
  const body = formatMetricCompact(unit, Math.abs(delta));
  const sign = delta > 0 ? '+' : delta < 0 ? '-' : '';
  return unit === 'KRW' ? `${sign}${body} 원` : `${sign}${body}${UNIT_LABELS[unit]}`;
}
