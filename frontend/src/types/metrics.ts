/**
 * 핵심지표 6개 — 기업분석 API 명세서 기준.
 * 키는 백엔드 metric.metric_code (V2__seed_metric.sql · V4__rename_average_metric_codes.sql) 와 같고,
 * /metrics/{metric} 경로변수·
 * keys 파라미터·응답 metrics[].key / series[].key 에 그대로 쓰인다.
 */
export const METRIC_KEYS = [
  'revenue',
  'operating_profit',
  'employee_count',
  'average_salary',
  'average_tenure',
  'rd_ratio',
] as const;

export type MetricKey = (typeof METRIC_KEYS)[number];

export const METRIC_LABELS: Record<MetricKey, string> = {
  revenue: '매출액',
  operating_profit: '영업이익',
  employee_count: '직원 수',
  average_salary: '1인 평균 급여',
  average_tenure: '평균 근속',
  rd_ratio: 'R&D / 매출',
};

/** 백엔드 응답의 unit 코드와 동일 (metric.unit CHECK 제약: KRW, PERSON, YEAR, %) */
export type MetricUnit = 'KRW' | 'PERSON' | 'YEAR' | '%';

export const METRIC_UNITS: Record<MetricKey, MetricUnit> = {
  revenue: 'KRW',
  operating_profit: 'KRW',
  employee_count: 'PERSON',
  average_salary: 'KRW',
  average_tenure: 'YEAR',
  rd_ratio: '%',
};

export const UNIT_LABELS: Record<MetricUnit, string> = {
  KRW: '원',
  PERSON: '명',
  YEAR: '년',
  '%': '%',
};

/**
 * 값의 의미: KRW 는 원, PERSON 은 명, YEAR 는 년(소수 허용), % 는 퍼센트 값 그대로 (8.3 → 8.3%).
 * 값이 없으면 null (0과 구분).
 */
export interface KeyMetric {
  key: MetricKey;
  value: number | null;
}
