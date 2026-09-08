import type { ComparisonMetricKey, CompanyTrend } from './types';

/** timeseries 에서 직접 받는 지표 키 (keys 파라미터). 나머지 두 개는 여기서 계산한다. */
export const TREND_SOURCE_KEYS = [
  'revenue',
  'operating_profit',
  'employee_count',
  'average_salary',
  'rd_ratio',
] as const;

/** 시계열 조회 구간. 서버가 응답의 range 로 알려준다. 화면에서 연도를 정하지 않는다. */
export interface TrendRange {
  from: number;
  to: number;
}

export const yearsOf = (range: TrendRange): number[] =>
  Array.from({ length: range.to - range.from + 1 }, (_, i) => range.from + i);

/** GET /metrics/timeseries 응답의 series[] 최소 형태 */
export interface TrendSeriesLike {
  key: string;
  points: Array<{ year: number; value: number | null }>;
}

const pct = (n: number) => Math.round(n * 10) / 10;

/** 구간을 모르는 기업(404)의 자리. 호출부가 다른 기업의 구간으로 채운다. */
export const emptyComparisonTrend = (corpCode: string, corpName: string): CompanyTrend => ({
  corpCode,
  corpName,
  years: [],
  values: {},
});

/**
 * 시계열 응답을 연도 × 비교 지표 표로 바꾼다.
 * - 연도 축은 응답의 range. 2021~2025 를 박아 두지 않는다
 * - revenue_growth: 전년 매출이 있을 때 (올해/전년 - 1) × 100
 * - operating_margin: 영업이익/매출 × 100 (둘 다 있을 때)
 * - 없는 값은 null (0 으로 채우지 않음)
 */
export function toComparisonTrend(
  corpCode: string,
  corpName: string,
  series: TrendSeriesLike[],
  range: TrendRange,
): CompanyTrend {
  const byKey = new Map<string, Map<number, number | null>>();
  for (const s of series) {
    const m = new Map<number, number | null>();
    for (const p of s.points ?? []) m.set(p.year, typeof p.value === 'number' ? p.value : null);
    byKey.set(s.key, m);
  }
  const get = (key: string, year: number): number | null => byKey.get(key)?.get(year) ?? null;

  const years = yearsOf(range);
  const values: CompanyTrend['values'] = {};
  for (const year of years) {
    const revenue = get('revenue', year);
    const prevRevenue = get('revenue', year - 1);
    const op = get('operating_profit', year);
    const row: Partial<Record<ComparisonMetricKey, number | null>> = {
      revenue,
      operating_profit: op,
      employee_count: get('employee_count', year),
      average_salary: get('average_salary', year),
      rd_ratio: get('rd_ratio', year),
      revenue_growth:
        revenue !== null && prevRevenue !== null && prevRevenue !== 0
          ? pct((revenue / prevRevenue - 1) * 100)
          : null,
      operating_margin:
        revenue !== null && op !== null && revenue !== 0 ? pct((op / revenue) * 100) : null,
    };
    values[year] = row;
  }
  return { corpCode, corpName, years, values };
}
