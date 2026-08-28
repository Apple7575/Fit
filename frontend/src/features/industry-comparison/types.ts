import type { MetricKey } from '../../types/metrics';

/** 비교 대상 기업 한 곳의 지표 값. 값이 없으면 null (0과 구분). */
export interface IndustryPeer {
  corpCode: string;
  corpName: string;
  value: number | null;
}

/**
 * 동일 산업 비교 한 건.
 * GET /api/companies/{corpCode}/metrics/{metric}/industry-comparison 응답에 대응한다.
 */
export interface IndustryComparison {
  metricKey: MetricKey;
  year: number;
  industryName: string | null;
  /** 지표 값 내림차순. 백엔드도 같은 순서로 내려준다. */
  peers: IndustryPeer[];
}
