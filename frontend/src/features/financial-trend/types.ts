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

/** 5년 추이 응답. 구간은 서버가 정한 값(range)을 그대로 쓴다. */
export interface FinancialTrend {
  from: number;
  to: number;
  series: TrendSeries[];
}

/**
 * 다른 feature(집중 분야·산업 비교)가 아직 요청 구간으로 쓰는 상수.
 * 이 feature 는 연도를 박지 않는다 — 요청에 to(기준연도)만 넘기고 from 은 서버가 정하며,
 * 화면의 연도 축은 응답의 range 만 쓴다. 다른 feature 도 range 를 따르게 되면 지운다.
 */
export const TREND_START_YEAR = 2021;
export const TREND_END_YEAR = 2025;
