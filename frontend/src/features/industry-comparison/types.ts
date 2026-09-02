import type { MetricUnit } from '../../types/metrics';

/**
 * 비교 지표 7종 — 산업 비교 API v2 가 주는 지표 그대로. 핵심지표 카탈로그(types/metrics)와 분리한다.
 * 키는 백엔드 metric_code 와 같고 keys/metrics 파라미터·응답 values 키에 그대로 쓰인다.
 */
export const COMPARISON_METRIC_KEYS = [
  'revenue',
  'revenue_growth',
  'operating_profit',
  'operating_margin',
  'employee_count',
  'average_salary',
  'rd_ratio',
] as const;

export type ComparisonMetricKey = (typeof COMPARISON_METRIC_KEYS)[number];

export const COMPARISON_METRIC_LABELS: Record<ComparisonMetricKey, string> = {
  revenue: '매출',
  revenue_growth: '매출 성장률',
  operating_profit: '영업이익',
  operating_margin: '영업이익률',
  employee_count: '직원 수',
  average_salary: '평균 급여',
  rd_ratio: 'R&D 비율',
};

export const COMPARISON_METRIC_UNITS: Record<ComparisonMetricKey, MetricUnit> = {
  revenue: 'KRW',
  revenue_growth: '%',
  operating_profit: 'KRW',
  operating_margin: '%',
  employee_count: 'PERSON',
  average_salary: 'KRW',
  rd_ratio: '%',
};

/** 비교 기업(peers) 최대 선택 수 — API 명세 peers 최대 3 (조회 기업 포함 4개 표시) */
export const MAX_PEERS = 3;

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

/** 비교 후보·선택 기업 (corpCode + 이름) */
export interface IndustryCompany {
  corpCode: string;
  corpName: string;
}

/** GET /insights?section=comparison 의 insights[] 한 건 (규칙 기반: 규모·수익성 등) */
export interface ComparisonInsight {
  title: string;
  body: string | null;
}

/** 비교 기업 한 곳의 연도별 지표 값 (5개년 꺾은선용). 값이 없는 해는 null. */
export interface CompanyTrend {
  corpCode: string;
  corpName: string;
  /** year → 지표 키 → 값 */
  values: Record<number, Partial<Record<ComparisonMetricKey, number | null>>>;
}
