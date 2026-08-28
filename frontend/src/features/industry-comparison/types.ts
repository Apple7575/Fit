import type { MetricKey } from '../../types/metrics';

/** 비교 대상 기업 한 곳의 지표 값. 값이 없으면 null (0과 구분). */
export interface IndustryPeer {
  corpCode: string;
  corpName: string;
  value: number | null;
}

/** 목록 정렬 방향. 값이 없는 기업은 방향과 무관하게 항상 마지막이다. */
export type SortOrder = 'desc' | 'asc';

/**
 * 지표 하나에 대한 동일 산업 비교.
 * GET /api/companies/{corpCode}/metrics/{metric}/industry-comparison 응답에 대응한다.
 */
export interface IndustryComparison {
  metricKey: MetricKey;
  year: number;
  industryName: string | null;
  peers: IndustryPeer[];
}
