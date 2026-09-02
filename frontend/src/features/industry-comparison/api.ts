import { apiGet } from '../../api/client';
import {
  emptyIndustryComparison,
  mockIndustryCompaniesByIndustry,
  mockIndustryComparisonByCompany,
} from '../../mocks/industryComparison';
import {
  COMPARISON_METRIC_KEYS,
  type ComparisonMetricKey,
  type IndustryCompany,
  type IndustryComparison,
} from './types';

/**
 * GET /api/companies/{corpCode}/industry-comparison 의 data 부분 (v2).
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

/** GET /api/industries/{industryCode}/companies 의 data 부분 */
export interface IndustryCompaniesResponse {
  industry: { code: string; name: string } | null;
  companies: Array<{ corpCode: string; corpName: string }>;
}

const KNOWN_KEYS: ReadonlySet<string> = new Set(COMPARISON_METRIC_KEYS);

const isComparisonKey = (key: string): key is ComparisonMetricKey =>
  KNOWN_KEYS.has(key);

/**
 * 응답을 화면 모델로 변환한다.
 * - 모르는 지표 키는 metrics 에서 제거 (선택 UI 가 "미제공" 판단에 쓴다)
 * - values 는 그대로 둔다 (조회 측이 아는 키로만 접근하므로 무해)
 * - 응답에 없는 배열은 빈 배열로
 */
export const toIndustryComparison = (
  response: IndustryComparisonResponse,
): IndustryComparison => ({
  year: response.year ?? null,
  industry: response.industry ?? null,
  metrics: (response.metrics ?? []).filter(isComparisonKey),
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

export interface ComparisonQuery {
  /** 비교할 기업 corpCode (최대 3). 비우면 서버 기본(대상 기업만) */
  peers?: readonly string[];
  /** 생략하면 서버가 그 기업의 최신 적재 연도로 맞춘다 */
  year?: number;
}

/**
 * year 를 생략하면 서버가 그 기업의 최신 적재 연도로 맞춘다.
 * 프론트가 연도를 박아 보내면 적재가 밀릴 때 기본정보·핵심지표와 다른 해를 비교하게 된다.
 * metrics 파라미터는 보내지 않는다 — 서버 기본(7종)을 받고, 프론트가 모르는 지표는 "미제공"으로 그린다.
 */
export async function fetchIndustryComparison(
  corpCode: string,
  signal?: AbortSignal,
  query: ComparisonQuery = {},
): Promise<IndustryComparison> {
  const peers = query.peers ?? [];

  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const base = mockIndustryComparisonByCompany[corpCode];
    if (!base) return emptyIndustryComparison;
    // 목업도 명세처럼 대상 기업 + 고른 peers 만 돌려준다
    const selected = new Set(peers);
    return {
      ...base,
      companies: base.companies.filter(
        (c) => c.isTarget || selected.has(c.corpCode),
      ),
    };
  }

  const params = new URLSearchParams();
  if (peers.length > 0) params.set('peers', peers.join(','));
  if (query.year !== undefined) params.set('year', String(query.year));
  const qs = params.toString();
  const data = await apiGet<IndustryComparisonResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/industry-comparison${qs ? `?${qs}` : ''}`,
    { signal },
  );
  return toIndustryComparison(data);
}

/**
 * 같은 산업 비교 후보 목록. 없는 industryCode 는 빈 배열 200.
 * 대상 기업 자신은 호출부가 제외한다.
 */
export async function fetchIndustryCompanies(
  industryCode: string,
  signal?: AbortSignal,
): Promise<IndustryCompany[]> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 200));
    return mockIndustryCompaniesByIndustry[industryCode] ?? [];
  }

  const data = await apiGet<IndustryCompaniesResponse>(
    `/api/industries/${encodeURIComponent(industryCode)}/companies?sort=revenue&limit=50`,
    { signal },
  );
  return (data.companies ?? []).map((c) => ({
    corpCode: c.corpCode,
    corpName: c.corpName,
  }));
}
