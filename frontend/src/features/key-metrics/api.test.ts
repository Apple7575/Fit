import { describe, expect, it } from 'vitest';
import { toKeyMetricsData, type KeyMetricsResponse } from './api';

const base: KeyMetricsResponse = {
  corpCode: '00126380',
  year: 2025,
  metrics: [
    { key: 'revenue', label: '매출액', unit: 'KRW', value: 100, yoy: { prevValue: 90, changeRate: 11.1 } },
    { key: 'net_income', label: '당기순이익', unit: 'KRW', value: null, yoy: null },
    { key: 'rd_ratio', label: 'R&D', unit: '%', value: 8.1, yoy: null },
    { key: 'unknown_metric', label: '?', unit: 'KRW', value: 1, yoy: null },
  ],
  profitability: { operatingMargin: 13.6, netMargin: null, debtRatio: 38.3 },
};

describe('toKeyMetricsData', () => {
  it('keeps only the six key metrics and carries the year-over-year rate', () => {
    const data = toKeyMetricsData(base);

    expect(data.year).toBe(2025);
    expect(data.metrics).toEqual([
      { key: 'revenue', value: 100, prevValue: 90, changeRate: 11.1 },
      { key: 'net_income', value: null, prevValue: null, changeRate: null },
    ]);
  });

  it('normalizes a partial profitability block and drops an all-null one', () => {
    expect(toKeyMetricsData(base).profitability).toEqual({
      operatingMargin: 13.6,
      netMargin: null,
      debtRatio: 38.3,
    });

    expect(
      toKeyMetricsData({ ...base, profitability: { operatingMargin: null } })
        .profitability,
    ).toBeNull();
    expect(
      toKeyMetricsData({ ...base, profitability: undefined }).profitability,
    ).toBeNull();
  });

  it('survives a response without metrics or year', () => {
    const data = toKeyMetricsData({
      corpCode: 'A',
      year: null,
      metrics: undefined as unknown as KeyMetricsResponse['metrics'],
    });
    expect(data).toEqual({ year: null, metrics: [], profitability: null });
  });
});
