import type { MetricKey } from '../../types/metrics';

/**
 * 한 연도의 값. 공시 누락 등으로 값이 없으면 null (0과 구분).
 * changeRate 는 전년 대비 증감률(%). 전년 값이 없거나 올해 값이 없으면 null.
 */
export interface TrendPoint {
  year: number;
  value: number | null;
  changeRate: number | null;
}

/** 지표 하나의 연도별 시계열. GET .../metrics/timeseries 응답의 series[] 요소에 대응 */
export interface TrendSeries {
  key: MetricKey;
  points: TrendPoint[];
}

export const TREND_START_YEAR = 2021;
export const TREND_END_YEAR = 2025;
