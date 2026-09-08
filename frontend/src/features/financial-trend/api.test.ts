import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchFinancialTrend, toFinancialTrend, toTrendSeries } from './api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('toFinancialTrend', () => {
  it('uses the range the server actually queried and fills missing years with null', () => {
    const trend = toFinancialTrend({
      range: { from: 2022, to: 2026 },
      series: [
        {
          key: 'revenue',
          label: '매출액',
          unit: 'KRW',
          points: [
            { year: 2022, value: 100, changeRate: null },
            { year: 2026, value: 140, changeRate: 7.7 },
          ],
        },
        { key: 'unknown_metric', label: '?', unit: 'KRW', points: [] },
      ],
    });

    expect(trend.from).toBe(2022);
    expect(trend.to).toBe(2026);
    expect(trend.series).toHaveLength(1);
    expect(trend.series[0].points.map((p) => p.year)).toEqual([2022, 2023, 2024, 2025, 2026]);
    expect(trend.series[0].points[0]).toEqual({ year: 2022, value: 100, changeRate: null });
    expect(trend.series[0].points[1]).toEqual({ year: 2023, value: null, changeRate: null });
    expect(trend.series[0].points[4]).toEqual({ year: 2026, value: 140, changeRate: 7.7 });
  });

  it('fills every year of the range even when a series has no points', () => {
    const [series] = toTrendSeries({
      range: { from: 2020, to: 2024 },
      series: [{ key: 'revenue', label: '', unit: 'KRW', points: [] }],
    });
    expect(series.points.map((p) => p.year)).toEqual([2020, 2021, 2022, 2023, 2024]);
    expect(series.points.every((p) => p.value === null)).toBe(true);
  });
});

describe('fetchFinancialTrend (실 API 경로)', () => {
  afterEach(() => vi.unstubAllGlobals());

  const stub = (range: { from: number; to: number } = { from: 2021, to: 2025 }) => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({ success: true, data: { range, series: [] } }),
    );
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  };

  it('기준연도가 없으면 구간을 보내지 않고 서버가 정한 range 를 따른다', async () => {
    const fetchMock = stub({ from: 2020, to: 2024 });

    const trend = await fetchFinancialTrend('00126380');

    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/companies/00126380/metrics/timeseries');
    expect(trend.from).toBe(2020);
    expect(trend.to).toBe(2024);
  });

  it('기준연도가 있으면 to 만 보내고 from 은 서버에 맡긴다', async () => {
    const fetchMock = stub();

    await fetchFinancialTrend('00126380', undefined, 2024);

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('?to=2024');
    expect(url).not.toContain('from=');
  });

  it('404 는 ApiError(COMPANY_NOT_FOUND) 로 던진다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json({ success: false, error: { code: 'COMPANY_NOT_FOUND', message: '없음' } }, 404),
      ),
    );

    await expect(fetchFinancialTrend('99999999')).rejects.toMatchObject({
      status: 404,
      code: 'COMPANY_NOT_FOUND',
    });
  });
});
