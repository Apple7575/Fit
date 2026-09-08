import { describe, expect, it } from 'vitest';
import { toComparisonTrend } from './trend';

describe('toComparisonTrend', () => {
  it('derives growth and margin per year and leaves gaps as null', () => {
    const trend = toComparisonTrend('A', '에이', [
      { key: 'revenue', points: [{ year: 2021, value: 100 }, { year: 2022, value: 120 }, { year: 2024, value: 150 }, { year: 2025, value: 0 }] },
      { key: 'operating_profit', points: [{ year: 2022, value: 12 }, { year: 2025, value: 3 }] },
      { key: 'rd_ratio', points: [{ year: 2021, value: 5.5 }] },
    ], { from: 2021, to: 2025 });

    expect(trend.values[2021]).toMatchObject({ revenue: 100, revenue_growth: null, operating_margin: null, rd_ratio: 5.5 });
    expect(trend.values[2022]).toMatchObject({ revenue_growth: 20, operating_margin: 10, employee_count: null });
    expect(trend.values[2023]).toMatchObject({ revenue: null, revenue_growth: null, operating_margin: null });
    // 2024: 전년(2023) 매출 없음 → 성장률 null, 영업이익 없음 → 이익률 null
    expect(trend.values[2024]).toMatchObject({ revenue: 150, revenue_growth: null, operating_margin: null });
    // 2025: 매출 0 → 0 으로 나누지 않는다
    expect(trend.values[2025]).toMatchObject({ revenue_growth: -100, operating_margin: null });
  });

  it('returns all-null rows for an empty series list', () => {
    const trend = toComparisonTrend('B', '비', [], { from: 2021, to: 2025 });
    expect(trend.years).toEqual([2021, 2022, 2023, 2024, 2025]);
    expect(Object.keys(trend.values)).toHaveLength(5);
    expect(Object.values(trend.values[2023]).every((v) => v === null)).toBe(true);
  });

  it('builds the year axis from the range the server returned', () => {
    const trend = toComparisonTrend(
      'C',
      '씨',
      [{ key: 'revenue', points: [{ year: 2026, value: 10 }] }],
      { from: 2022, to: 2026 },
    );
    expect(trend.years).toEqual([2022, 2023, 2024, 2025, 2026]);
    expect(trend.values[2021]).toBeUndefined();
    expect(trend.values[2026]).toMatchObject({ revenue: 10, revenue_growth: null });
  });
});
