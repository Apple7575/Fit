import { ApiError, apiGet } from '../../api/client';
import {
  emptyIndustryComparison,
  mockComparisonInsightsByCompany,
  mockComparisonTrendRange,
  mockComparisonTrendSeriesByCompany,
  mockIndustryCompaniesByIndustry,
  mockIndustryComparisonByCompany,
} from '../../mocks/industryComparison';
import {
  emptyComparisonTrend,
  toComparisonTrend,
  TREND_SOURCE_KEYS,
  type TrendRange,
  type TrendSeriesLike,
} from './trend';
import {
  COMPARISON_METRIC_KEYS,
  type ComparisonInsight,
  type ComparisonMetricKey,
  type CompanyTrend,
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

/** GET /api/companies/{corpCode}/insights?section=comparison 의 data 부분 */
export interface InsightsResponse {
  section?: string;
  insights?: Array<{ title?: string | null; body?: string | null }>;
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

/** title 이 없는 인사이트는 body 를 제목으로 올린다. 둘 다 없으면 버린다. */
export const toComparisonInsights = (response: InsightsResponse): ComparisonInsight[] =>
  (response.insights ?? []).flatMap((item) => {
    const title = item.title?.trim() || item.body?.trim() || '';
    if (!title) return [];
    const body = item.title?.trim() ? item.body?.trim() || null : null;
    return [{ title, body }];
  });

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const USE_MOCK =
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export interface ComparisonQuery {
  /** 비교할 기업 corpCode (최대 3). 비우면 서버 기본(대상 기업만) */
  peers?: readonly string[];
  /** 생략하면 서버가 그 기업의 최신 적재 연도로 맞춘다 */
  year?: number;
}

const peersParam = (peers: readonly string[]) =>
  peers.length > 0 ? `peers=${encodeURIComponent(peers.join(','))}` : '';

/** 목업 전용: 후보 목록에서 이름을 찾고 없으면 코드로 대체 */
function mockCompanyName(corpCode: string): string {
  for (const list of Object.values(mockIndustryCompaniesByIndustry)) {
    const hit = list.find((c) => c.corpCode === corpCode);
    if (hit) return hit.corpName;
  }
  return corpCode;
}

/**
 * year 를 생략하면 서버가 그 기업의 최신 적재 연도로 맞춘다.
 * 프론트가 연도를 박아 보내면 적재가 밀릴 때 기본정보·핵심지표와 다른 해를 비교하게 된다.
 * metrics 파라미터는 보내지 않는다 — 서버 기본(7종)을 받는다.
 */
export async function fetchIndustryComparison(
  corpCode: string,
  signal?: AbortSignal,
  query: ComparisonQuery = {},
): Promise<IndustryComparison> {
  const peers = query.peers ?? [];

  if (USE_MOCK) {
    await delay(400);
    const base = mockIndustryComparisonByCompany[corpCode];
    if (!base) return emptyIndustryComparison;
    // 목업도 명세처럼 조회 기업 + 고른 peers 만 돌려준다 (목업에 없는 기업은 값 없이 이름만)
    const known = new Map(base.companies.map((c) => [c.corpCode, c]));
    const chosen = peers.map(
      (code) =>
        known.get(code) ?? {
          corpCode: code,
          corpName: mockCompanyName(code),
          isTarget: false,
          values: {},
        },
    );
    return {
      ...base,
      companies: [...base.companies.filter((c) => c.isTarget), ...chosen],
    };
  }

  const params: string[] = [peersParam(peers)];
  if (query.year !== undefined) params.push(`year=${query.year}`);
  const qs = params.filter(Boolean).join('&');
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
    await delay(200);
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

/**
 * 비교 핵심 인사이트 (명세 P2, 요청 시 규칙으로 생성). peers 가 없으면 조회하지 않는다.
 * 404·빈 응답은 호출부가 섹션을 숨긴다.
 */
export async function fetchComparisonInsights(
  corpCode: string,
  peers: readonly string[],
  signal?: AbortSignal,
): Promise<ComparisonInsight[]> {
  if (peers.length === 0) return [];

  if (USE_MOCK) {
    await delay(500);
    return mockComparisonInsightsByCompany[corpCode] ?? [];
  }

  const qs = ['section=comparison', peersParam(peers)].filter(Boolean).join('&');
  const data = await apiGet<InsightsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/insights?${qs}`,
    { signal },
  );
  return toComparisonInsights(data);
}

/** GET /metrics/timeseries 의 data 부분 (여기서 쓰는 필드만). range 는 서버가 실제로 조회한 구간이다. */
interface TimeseriesResponse {
  range: TrendRange;
  series?: TrendSeriesLike[];
}

/**
 * 비교 기업 한 곳의 5개년 지표. timeseries 를 keys=5종 으로 한 번 부르고,
 * 매출 성장률·영업이익률은 시계열에서 계산한다. 기업이 없으면(404) 구간을 모르므로 빈 행으로 돌리고,
 * 호출부(fetchComparisonTrends)가 다른 기업의 구간으로 채워 선이 사라지지 않게 한다.
 *
 * 구간(from·to)은 보내지 않는다. 비교 조회(/industry-comparison)도 연도를 생략하므로 둘 다
 * 서버가 같은 기준연도로 맞추고, 화면은 응답의 range 를 연도 축으로 쓴다.
 */
export async function fetchComparisonTrend(
  company: IndustryCompany,
  signal?: AbortSignal,
): Promise<CompanyTrend> {
  if (USE_MOCK) {
    await delay(300);
    return toComparisonTrend(
      company.corpCode,
      company.corpName,
      mockComparisonTrendSeriesByCompany[company.corpCode] ?? [],
      mockComparisonTrendRange,
    );
  }

  const params = new URLSearchParams({ keys: TREND_SOURCE_KEYS.join(',') });
  try {
    const data = await apiGet<TimeseriesResponse>(
      `/api/companies/${encodeURIComponent(company.corpCode)}/metrics/timeseries?${params}`,
      { signal },
    );
    return toComparisonTrend(company.corpCode, company.corpName, data.series ?? [], data.range);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return emptyComparisonTrend(company.corpCode, company.corpName);
    }
    throw error;
  }
}

/**
 * 선택된 기업 전부의 5개년 지표를 병렬로. 하나라도 5xx 면 전체 실패(재시도 안내).
 * 404 로 구간을 못 받은 기업은 다른 기업이 받은 구간으로 값 없는 행을 만들어 같은 축에 놓는다.
 */
export async function fetchComparisonTrends(
  companies: IndustryCompany[],
  signal?: AbortSignal,
): Promise<CompanyTrend[]> {
  const trends = await Promise.all(companies.map((c) => fetchComparisonTrend(c, signal)));
  const known = trends.find((t) => t.years.length > 0);
  if (!known) return trends;
  const range = { from: known.years[0], to: known.years[known.years.length - 1] };
  return trends.map((t) =>
    t.years.length > 0 ? t : toComparisonTrend(t.corpCode, t.corpName, [], range),
  );
}
