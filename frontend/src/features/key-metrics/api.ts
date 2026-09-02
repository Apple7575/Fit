import { ApiError, apiGet } from '../../api/client';
import { mockKeyMetricsByCompany } from '../../mocks/keyMetrics';
import {
  KEY_METRIC_KEYS,
  type KeyMetric,
  type KeyMetricsData,
  type MetricKey,
  type Profitability,
} from '../../types/metrics';

/**
 * GET /api/companies/{corpCode}/metrics?year=YYYY 의 data 부분 (v2).
 * 백엔드 CompanyMetricsResponse 와 같다. year 는 적재값이 없으면 null.
 * 값 없는 지표도 배열에서 자리를 유지하고 value 는 null (0 변환 금지).
 */
export interface KeyMetricsResponse {
  corpCode: string;
  year: number | null;
  metrics: Array<{
    key: string;
    label: string;
    value: number | null;
    unit: string;
    yoy: { prevValue: number | null; changeRate: number | null } | null;
  }>;
  profitability?: Partial<Profitability> | null;
}

const KEY_METRIC_SET: ReadonlySet<string> = new Set(KEY_METRIC_KEYS);

const isKeyMetricKey = (key: string): key is MetricKey => KEY_METRIC_SET.has(key);

/** 응답에서 핵심지표 6종만 추려 화면 모델로 변환한다. 모르는 키는 무시. */
export const toKeyMetrics = (response: KeyMetricsResponse): KeyMetric[] =>
  (response.metrics ?? []).flatMap((m) =>
    isKeyMetricKey(m.key)
      ? [{ key: m.key, value: m.value ?? null, changeRate: m.yoy?.changeRate ?? null }]
      : [],
  );

/** profitability 블록이 없거나 전부 null 이면 null (섹션 미노출 판단용). */
export const toProfitability = (
  response: KeyMetricsResponse,
): Profitability | null => {
  const p = response.profitability;
  if (!p) return null;
  const result: Profitability = {
    operatingMargin: p.operatingMargin ?? null,
    netMargin: p.netMargin ?? null,
    debtRatio: p.debtRatio ?? null,
  };
  return Object.values(result).every((v) => v === null) ? null : result;
};

export const toKeyMetricsData = (response: KeyMetricsResponse): KeyMetricsData => ({
  year: response.year ?? null,
  metrics: toKeyMetrics(response),
  profitability: toProfitability(response),
});

/**
 * 백엔드 없이 mock 으로 동작할지 여부.
 * - VITE_API_MOCK=true  → 항상 mock
 * - VITE_API_MOCK=false → 항상 실제 API
 * - 미설정              → 개발 서버(npm run dev)에서만 mock, 빌드 결과물은 실제 API
 * (.env.* 는 gitignore 대상이라 기본값을 코드에 둔다. 로컬에서 바꾸려면 .env.development.local)
 */
const USE_MOCK =
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

/**
 * year 를 생략하면 서버가 최신 연도를 고른다 (명세: year 선택, 기본 최신).
 * 기준연도는 기업 기본정보의 dataYear 를 따르는 것이 원칙이라 호출부가 넘겨준다.
 */
export async function fetchKeyMetrics(
  corpCode: string,
  year?: number | null,
  signal?: AbortSignal,
): Promise<KeyMetricsData> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const data = mockKeyMetricsByCompany[corpCode];
    if (!data) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return data;
  }

  const params = new URLSearchParams();
  if (year != null) params.set('year', String(year));
  const qs = params.toString();
  const query = qs ? `?${qs}` : '';
  const data = await apiGet<KeyMetricsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/metrics${query}`,
    { signal },
  );
  return toKeyMetricsData(data);
}
