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
    case 'KRW':
      return formatAmount(value);
    case 'PERSON':
      return Math.round(value).toLocaleString('ko-KR');
    case 'YEAR':
    case '%':
      return oneDecimal(value);
  }
}

export const metricUnit = (key: MetricKey): MetricUnit => METRIC_UNITS[key];

export const metricUnitLabel = (key: MetricKey): string =>
  UNIT_LABELS[METRIC_UNITS[key]];

/** 지표 키 기준으로 숫자만 포맷 (예: revenue → "300조 8,709억", average_tenure → "12.4") */
export const formatMetricValue = (key: MetricKey, value: number): string =>
  formatMetricNumber(METRIC_UNITS[key], value);

/** 숫자 + 단위 (예: "300조 8,709억 원", "124,804 명", "12.4 년", "8.3 %") */
export const formatMetricWithUnit = (key: MetricKey, value: number): string =>
  `${formatMetricValue(key, value)} ${metricUnitLabel(key)}`;

/**
 * 카드·차트용 짧은 표기. KRW 는 조/억/만 중 가장 큰 단위 하나만 소수점 1자리로
 * (300.9조, 1.2억, 501만), 나머지는 formatMetricNumber 와 같다.
 */
export function formatMetricCompact(unit: MetricUnit, value: number): string {
  if (unit !== 'KRW') return formatMetricNumber(unit, value);
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  const oneDp = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));
  if (abs >= 1_0000_0000_0000) return `${sign}${oneDp(abs / 1_0000_0000_0000)}조`;
  if (abs >= 1_0000_0000) return `${sign}${oneDp(abs / 1_0000_0000)}억`;
  if (abs >= 1_0000) return `${sign}${oneDp(abs / 1_0000)}만`;
  return `${sign}${abs.toLocaleString('ko-KR')}`;
}

export const formatMetricCompactValue = (key: MetricKey, value: number): string =>
  formatMetricCompact(METRIC_UNITS[key], value);
