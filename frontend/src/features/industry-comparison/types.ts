import type { MetricUnit } from '../../types/metrics';

/**
 * 비교 지표 10종 — Jira(80) 기본 비교 항목. 핵심지표 카탈로그(types/metrics)와 분리한다.
 * 키는 백엔드 metric_code 와 같다. API v2 는 이 중 7종(revenue, revenue_growth,
 * operating_profit, operating_margin, employee_count, average_salary, rd_ratio)만 주므로
 * 나머지(순이익·부채비율·직원 증가율·평균 근속)는 값이 올 때까지 "미제공"으로 표시한다.
 */
export const COMPARISON_METRIC_KEYS = [
  'revenue',
  'revenue_growth',
  'operating_profit',
  'operating_margin',
  'net_income',
  'debt_ratio',
  'employee_count',
  'employee_growth',
  'average_salary',
  'average_tenure',
] as const;

export type ComparisonMetricKey = (typeof COMPARISON_METRIC_KEYS)[number];

export const COMPARISON_METRIC_LABELS: Record<ComparisonMetricKey, string> = {
  revenue: '매출액',
  revenue_growth: '매출 성장률',
  operating_profit: '영업이익',
  operating_margin: '영업이익률',
  net_income: '순이익',
  debt_ratio: '부채비율',
  employee_count: '직원 수',
  employee_growth: '직원 증가율',
  average_salary: '1인 평균 급여',
  average_tenure: '평균 근속',
};

export const COMPARISON_METRIC_UNITS: Record<ComparisonMetricKey, MetricUnit> = {
  revenue: 'KRW',
  revenue_growth: '%',
  operating_profit: 'KRW',
  operating_margin: '%',
  net_income: 'KRW',
  debt_ratio: '%',
  employee_count: 'PERSON',
  employee_growth: '%',
  average_salary: 'KRW',
  average_tenure: 'YEAR',
};

/** 비교 기업(peers) 최대 선택 수 — API 명세 peers 최대 3 */
export const MAX_PEERS = 3;

/** 목록 정렬 방향. 값이 없는 기업은 방향과 무관하게 항상 마지막이다. */
export type SortOrder = 'desc' | 'asc';

/** 비교군 산업. KSIC 중분류(2자리) 기준. */
export interface IndustryInfo {
  code: string;
  name: string;
  /** 같은 산업에 속한 전체 기업 수 (목록에 실린 수보다 클 수 있다) */
  companyCount: number;
}

/** 비교 대상 기업 한 곳. values 는 지표 키 → 값, 없으면 null (0과 구분). */
export interface ComparisonCompany {
  corpCode: string;
  corpName: string;
  /** 지금 보고 있는 기업이면 true. 목록에 반드시 포함된다. */
  isTarget: boolean;
  values: Partial<Record<ComparisonMetricKey, number | null>>;
}

/**
 * 동일 산업 비교 응답.
 * GET /api/companies/{corpCode}/industry-comparison 의 data 부분과 같다.
 * 비교 대상이 없으면 companies 는 빈 배열(200)이다.
 */
export interface IndustryComparison {
  /** 서버가 정한 기준연도. 적재된 값이 없는 기업이면 null */
  year: number | null;
  industry: IndustryInfo | null;
  /** 이 응답에 값이 실린 지표 키. 여기 없는 지표는 전 기업 "미제공". */
  metrics: ComparisonMetricKey[];
  companies: ComparisonCompany[];
}

/** 비교 후보 기업 (GET /api/industries/{industryCode}/companies 의 companies[]) */
export interface IndustryCompany {
  corpCode: string;
  corpName: string;
}

/** 선택한 지표 하나로 펼친 목록 행. 정렬·막대 계산의 단위. */
export interface IndustryPeer {
  corpCode: string;
  corpName: string;
  isTarget?: boolean;
  value: number | null;
}
