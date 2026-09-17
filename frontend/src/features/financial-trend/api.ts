import { ApiError, apiGet } from '../../api/client';
import { mockFinancialTrendByCompany } from '../../mocks/financialTrend';
import { METRIC_KEYS, type MetricKey } from '../../types/metrics';
import type { FinancialTrend, TrendPoint, TrendSeries } from './types';

/**
 * GET /api/companies/{corpCode}/metrics/timeseries 의 data 부분 (v2).
 * 백엔드 MetricTimeseriesResponse 와 같다 (range + series, series 순서는 카탈로그 display_order).
 * range 는 서버가 실제로 조회한 구간이다 — to 를 생략하면 서버 기준연도, from 을 생략하면 to-4.
 * v2 에서 points[].changeRate 가 추가됐다 (전년 없으면 null).
 */
export interface FinancialTrendResponse {
  range: { from: number; to: number };
  series: Array<{
    key: string;
    label: string;
    unit: string;
    points: Array<{ year: number; value: number | null; changeRate?: number | null }>;
  }>;
}

const isMetricKey = (key: string): key is MetricKey =>
  (METRIC_KEYS as readonly string[]).includes(key);

/**
 * 응답을 화면 모델로 변환한다.
 * - 모르는 지표 키는 무시
 * - 응답에 빠진 연도는 null 로 채워 항상 from~to 전 구간을 갖게 한다 (누락 연도 렌더링 오류 방지)
 * - 숫자가 아닌 값(undefined, 문자열 등)은 null 로 취급 (changeRate 도 동일)
 * - 구간을 넘기지 않으면 응답의 range 를 쓴다 (서버가 항상 실제 조회 구간을 실어 보낸다)
 */
export const toTrendSeries = (
  response: FinancialTrendResponse,
  from = response.range.from,
  to = response.range.to,
): TrendSeries[] =>
  (response.series ?? [])
    .filter((s) => isMetricKey(s.key))
    .map((s) => {
      const byYear = new Map<number, { value: number | null; changeRate: number | null }>();
      for (const p of s.points ?? []) {
        byYear.set(p.year, {
          value: typeof p.value === 'number' ? p.value : null,
          changeRate: typeof p.changeRate === 'number' ? p.changeRate : null,
        });
      }
      const points: TrendPoint[] = [];
      for (let year = from; year <= to; year += 1) {
        const p = byYear.get(year);
        points.push({
          year,
          value: p?.value ?? null,
          changeRate: p?.changeRate ?? null,
        });
      }
      return { key: s.key as MetricKey, points };
    });

export const toFinancialTrend = (response: FinancialTrendResponse): FinancialTrend => ({
  from: response.range.from,
  to: response.range.to,
  series: toTrendSeries(response),
});

/** 목업 시계열의 구간. 목업 데이터가 가진 연도의 양 끝이다 (연도를 따로 박지 않는다). */
const mockRangeOf = (series: TrendSeries[]): { from: number; to: number } => {
  const years = series.flatMap((s) => s.points.map((p) => p.year));
  return { from: Math.min(...years), to: Math.max(...years) };
};

/**
 * VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일. 테스트에서 stubEnv 로 바꿀 수 있게 호출 시점에 평가한다.
 * 이름이 use 로 시작하면 oxlint 가 React Hook 으로 오인하므로 isMockEnabled 로 명명한다.
 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

/**
 * 최근 5년 시계열. 기준연도(to)는 기본정보의 dataYear 를 넘겨 KPI 카드와 같은 해로 맞춘다.
 * to 가 없으면(기본정보 실패 등) 서버가 정한 기준연도를 따르고, from 은 언제나 서버가 to-4 로 정한다.
 * 연도 축은 응답의 range 로 그린다.
 */
export async function fetchFinancialTrend(
  corpCode: string,
  signal?: AbortSignal,
  to?: number | null,
): Promise<FinancialTrend> {
  if (isMockEnabled()) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    const series = mockFinancialTrendByCompany[corpCode];
    if (!series) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return { ...mockRangeOf(series), series };
  }

  const params = new URLSearchParams();
  if (to != null) params.set('to', String(to));
  const qs = params.toString();
  const data = await apiGet<FinancialTrendResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/metrics/timeseries${qs ? `?${qs}` : ''}`,
    { signal },
  );
  return toFinancialTrend(data);
}
