import { METRIC_KEYS, type MetricKey } from '../../types/metrics';

/** 비교 지표 — 핵심지표 6종 전부. 응답 metrics 가 비어 있을 때의 기본 선택지. */
export const COMPARISON_METRIC_KEYS: readonly MetricKey[] = METRIC_KEYS;

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
  values: Partial<Record<MetricKey, number | null>>;
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
  /** 이 응답에 값이 실린 지표 키(6종). 선택 UI 는 이 목록만 보여준다. */
  metrics: MetricKey[];
  companies: ComparisonCompany[];
}

/** 선택한 지표 하나로 펼친 목록 행. 정렬·막대 계산의 단위. */
export interface IndustryPeer {
  corpCode: string;
  corpName: string;
  isTarget?: boolean;
  value: number | null;
}
