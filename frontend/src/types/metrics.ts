/**
 * 핵심지표 6개 — 기업분석 API 명세서 기준.
 * 키 문자열은 API 의 {metric} / keys 파라미터와 응답 metrics[].key 에 그대로 쓰인다 (BE 와 합의 필요).
 */
export const METRIC_KEYS = [
  'revenue',
  'operatingProfit',
  'employeeCount',
  'averageSalary',
  'averageTenure',
  'rndToRevenueRatio',
] as const;

export type MetricKey = (typeof METRIC_KEYS)[number];

export const METRIC_LABELS: Record<MetricKey, string> = {
  revenue: '매출액',
  operatingProfit: '영업이익',
  employeeCount: '직원 수',
  averageSalary: '1인 평균 급여',
  averageTenure: '평균 근속',
  rndToRevenueRatio: 'R&D / 매출',
};

/** 값의 종류. 포맷·단위 표기가 여기에 따라 달라진다 */
export type MetricUnit = 'krw' | 'person' | 'year' | 'percent';

export const METRIC_UNITS: Record<MetricKey, MetricUnit> = {
  revenue: 'krw',
  operatingProfit: 'krw',
  employeeCount: 'person',
  averageSalary: 'krw',
  averageTenure: 'year',
  rndToRevenueRatio: 'percent',
};

export const UNIT_LABELS: Record<MetricUnit, string> = {
  krw: '원',
  person: '명',
  year: '년',
  percent: '%',
};

/**
 * 값의 의미: krw 는 원, person 은 명, year 는 년(소수 허용), percent 는 % 값 그대로 (8.3 → 8.3%).
 * 값이 없으면 null (0과 구분).
 */
export interface KeyMetric {
  key: MetricKey;
  value: number | null;
}
