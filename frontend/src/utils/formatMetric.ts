import {
  METRIC_UNITS,
  UNIT_LABELS,
  type MetricKey,
  type MetricUnit,
} from '../types/metrics';
import { formatAmount } from './formatAmount';

/** 소수점 1자리까지, 불필요한 .0 은 뗀다 (12.0 → "12", 12.4 → "12.4") */
const oneDecimal = (n: number) =>
  Number.isInteger(n) ? n.toLocaleString('ko-KR') : n.toFixed(1);

/** 단위 문자 없이 숫자 부분만 포맷한다. 단위는 metricUnitLabel 로 따로 붙인다 */
export function formatMetricNumber(unit: MetricUnit, value: number): string {
  switch (unit) {
    case 'krw':
      return formatAmount(value);
    case 'person':
      return Math.round(value).toLocaleString('ko-KR');
    case 'year':
    case 'percent':
      return oneDecimal(value);
  }
}

export const metricUnit = (key: MetricKey): MetricUnit => METRIC_UNITS[key];

export const metricUnitLabel = (key: MetricKey): string =>
  UNIT_LABELS[METRIC_UNITS[key]];

/** 지표 키 기준으로 숫자만 포맷 (예: revenue → "300조 8,709억", averageTenure → "12.4") */
export const formatMetricValue = (key: MetricKey, value: number): string =>
  formatMetricNumber(METRIC_UNITS[key], value);

/** 숫자 + 단위 (예: "300조 8,709억 원", "124,804 명", "12.4 년", "8.3 %") */
export const formatMetricWithUnit = (key: MetricKey, value: number): string =>
  `${formatMetricValue(key, value)} ${metricUnitLabel(key)}`;
