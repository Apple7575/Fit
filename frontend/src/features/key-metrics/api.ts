import { ApiError, apiGet } from '../../api/client';
import { mockKeyMetricsByCompany } from '../../mocks/keyMetrics';
import { METRIC_KEYS, type KeyMetric, type MetricKey } from '../../types/metrics';

/**
 * GET /api/companies/{corpCode}/metrics?year=YYYY 의 data 부분.
 * 백엔드 CompanyMetricsResponse 와 같다. year 는 적재값이 없으면 null.
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
}

const isMetricKey = (key: string): key is MetricKey =>
  (METRIC_KEYS as readonly string[]).includes(key);

/** 응답에서 지원 지표 6개만 추려 화면 모델로 변환한다. 모르는 키는 무시. */
export const toKeyMetrics = (response: KeyMetricsResponse): KeyMetric[] =>
  response.metrics.flatMap((m) =>
    isMetricKey(m.key) ? [{ key: m.key, value: m.value }] : [],
  );

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

export async function fetchKeyMetrics(
  corpCode: string,
  year: number,
  signal?: AbortSignal,
): Promise<KeyMetric[]> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const metrics = mockKeyMetricsByCompany[corpCode];
    if (!metrics) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return metrics;
  }

  const params = new URLSearchParams({ year: String(year) });
  const data = await apiGet<KeyMetricsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/metrics?${params}`,
    { signal },
  );
  return toKeyMetrics(data);
}
