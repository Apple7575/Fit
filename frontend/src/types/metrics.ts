/**
 * 지표 카탈로그 — 기업분석 API 명세서 기준.
 * 키는 백엔드 metric.metric_code (V2__seed_metric.sql · V4__rename_average_metric_codes.sql) 와 같고,
 * keys 파라미터·응답 metrics[].key / series[].key 에 그대로 쓰인다.
 * rd_ratio 는 /metrics v2 에서 빠졌지만 산업 비교 API 가 아직 쓰므로 카탈로그에는 남긴다.
 */
export const METRIC_KEYS = [
  'revenue',
  'operating_profit',
  'net_income',
  'employee_count',
  'average_salary',
  'average_tenure',
  'rd_ratio',
] as const;

export type MetricKey = (typeof METRIC_KEYS)[number];

/**
 * 핵심지표·5년 추이 화면이 쓰는 6종 (/metrics v2, 성장 분석 표시 항목과 같다).
 * 순서가 곧 카드·선택지 순서다.
 */
export const KEY_METRIC_KEYS = [
  'revenue',
  'operating_profit',
  'net_income',
  'employee_count',
  'average_salary',
  'average_tenure',
] as const satisfies readonly MetricKey[];

export const METRIC_LABELS: Record<MetricKey, string> = {
  revenue: '매출액',
  operating_profit: '영업이익',
  net_income: '당기순이익',
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
  net_income: 'KRW',
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
 * 값이 없으면 null (0과 구분). changeRate 는 전년 대비 증감률(%), 전년 값이 없으면 null.
 * prevValue 는 전년 값 (증감액 계산용).
 */
export interface KeyMetric {
  key: MetricKey;
  value: number | null;
  prevValue: number | null;
  changeRate: number | null;
}

/** /metrics v2 의 profitability 블록. 값은 % 그대로, 없으면 null. */
export interface Profitability {
  operatingMargin: number | null;
  netMargin: number | null;
  debtRatio: number | null;
}

export const PROFITABILITY_LABELS: Record<keyof Profitability, string> = {
  operatingMargin: '영업이익률',
  netMargin: '순이익률',
  debtRatio: '부채비율',
};

/** 핵심지표 화면 모델. year 는 서버가 실제로 쓴 기준연도(적재값 없으면 null). */
export interface KeyMetricsData {
  year: number | null;
  metrics: KeyMetric[];
  profitability: Profitability | null;
}
