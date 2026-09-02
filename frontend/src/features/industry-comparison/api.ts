import { apiGet } from '../../api/client';
import {
  emptyIndustryComparison,
  mockIndustryComparisonByCompany,
} from '../../mocks/industryComparison';
import { METRIC_KEYS, type MetricKey } from '../../types/metrics';
import type { IndustryComparison } from './types';

/**
 * GET /api/companies/{corpCode}/industry-comparison?year=YYYY 의 data 부분.
 * 백엔드 IndustryComparisonResponse 와 같다. metrics 는 서버가 아는 지표 슬러그라
 * 프론트가 모르는 키가 섞여 올 수 있다.
 */
export interface IndustryComparisonResponse {
  /** 적재된 값이 없는 기업이면 null */
  year: number | null;
  industry: { code: string; name: string; companyCount: number } | null;
  metrics: string[];
  companies: Array<{
    corpCode: string;
    corpName: string;
    isTarget: boolean;
    values: Record<string, number | null>;
  }>;
}

const isMetricKey = (key: string): key is MetricKey =>
  (METRIC_KEYS as readonly string[]).includes(key);

/**
 * 응답을 화면 모델로 변환한다.
 * - 모르는 지표 키는 metrics 에서 제거 (선택 UI 에 노출되지 않게)
 * - values 는 그대로 둔다 (조회 측이 아는 키로만 접근하므로 무해)
 */
export const toIndustryComparison = (
  response: IndustryComparisonResponse,
): IndustryComparison => ({
  year: response.year,
  industry: response.industry,
  metrics: (response.metrics ?? []).filter(isMetricKey),
  companies: (response.companies ?? []).map((company) => ({
    corpCode: company.corpCode,
    corpName: company.corpName,
    isTarget: company.isTarget,
    values: company.values ?? {},
  })),
});

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const USE_MOCK =
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

/**
 * year 를 생략하면 서버가 그 기업의 최신 적재 연도로 맞춘다.
 * 프론트가 연도를 박아 보내면 적재가 밀릴 때 기본정보·핵심지표와 다른 해를 비교하게 된다.
 */
export async function fetchIndustryComparison(
  corpCode: string,
  signal?: AbortSignal,
  year?: number,
): Promise<IndustryComparison> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return mockIndustryComparisonByCompany[corpCode] ?? emptyIndustryComparison;
  }

  const query = year === undefined ? '' : `?year=${year}`;
  const data = await apiGet<IndustryComparisonResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/industry-comparison${query}`,
    { signal },
  );
  return toIndustryComparison(data);
}
