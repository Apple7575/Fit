import { ApiError, apiGet } from '../../api/client';
import { mockFinancialTrendByCompany } from '../../mocks/financialTrend';
import { METRIC_KEYS, type MetricKey } from '../../types/metrics';
import {
  TREND_END_YEAR,
  TREND_START_YEAR,
  type TrendPoint,
  type TrendSeries,
} from './types';

/**
 * GET /api/companies/{corpCode}/metrics/timeseries?from=2021&to=2025 의 data 부분.
 * ⚠ 백엔드 미구현 상태에서 명세(series[6] × points[5])를 바탕으로 가정한 형태. BE 완성 시 대조 필요.
 */
export interface FinancialTrendResponse {
  corpCode: string;
  from: number;
  to: number;
  series: Array<{
    key: string;
    points: Array<{ year: number; value: number | null }>;
  }>;
}

const isMetricKey = (key: string): key is MetricKey =>
  (METRIC_KEYS as readonly string[]).includes(key);

/**
 * 응답을 화면 모델로 변환한다.
 * - 모르는 지표 키는 무시
 * - 응답에 빠진 연도는 null 로 채워 항상 from~to 전 구간을 갖게 한다 (누락 연도 렌더링 오류 방지)
 * - 숫자가 아닌 값(undefined, 문자열 등)은 null 로 취급
 */
export const toTrendSeries = (
  response: FinancialTrendResponse,
  from = TREND_START_YEAR,
  to = TREND_END_YEAR,
): TrendSeries[] =>
  (response.series ?? [])
    .filter((s) => isMetricKey(s.key))
    .map((s) => {
      const valueByYear = new Map<number, number | null>();
      for (const p of s.points ?? []) {
        valueByYear.set(p.year, typeof p.value === 'number' ? p.value : null);
      }
      const points: TrendPoint[] = [];
      for (let year = from; year <= to; year += 1) {
        points.push({ year, value: valueByYear.get(year) ?? null });
      }
      return { key: s.key as MetricKey, points };
    });

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const USE_MOCK =
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchFinancialTrend(
  corpCode: string,
  signal?: AbortSignal,
  from = TREND_START_YEAR,
  to = TREND_END_YEAR,
): Promise<TrendSeries[]> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const series = mockFinancialTrendByCompany[corpCode];
    if (!series) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return series;
  }

  const params = new URLSearchParams({ from: String(from), to: String(to) });
  const data = await apiGet<FinancialTrendResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/metrics/timeseries?${params}`,
    { signal },
  );
  return toTrendSeries(data, from, to);
}
