import type { MetricKey } from '../../types/metrics';

/** 한 연도의 값. 공시 누락 등으로 값이 없으면 null (0과 구분). */
export interface TrendPoint {
  year: number;
  value: number | null;
}

/** 지표 하나의 연도별 시계열. GET .../metrics/timeseries 응답의 series[] 요소에 대응 */
export interface TrendSeries {
  key: MetricKey;
  points: TrendPoint[];
}

export const TREND_START_YEAR = 2021;
export const TREND_END_YEAR = 2025;
