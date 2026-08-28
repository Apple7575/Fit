import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { KeyMetricsSection } from './KeyMetricsSection';

const okBody = (corpCode: string, revenue: number | null) => ({
  success: true,
  data: {
    corpCode,
    year: 2025,
    metrics: [
      { key: 'revenue', value: revenue },
      { key: 'operatingProfit', value: 6_566_976_000_000 },
      { key: 'netIncome', value: 15_487_100_000_000 },
      { key: 'totalAssets', value: 455_905_980_000_000 },
      { key: 'totalLiabilities', value: 92_228_115_000_000 },
      { key: 'totalEquity', value: 363_677_865_000_000 },
    ],
  },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('KeyMetricsSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state, then the values returned by the API', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json(okBody('00126380', 300_870_903_000_000)));
    vi.stubGlobal('fetch', fetchMock);

    render(<KeyMetricsSection corpCode="00126380" year={2025} />);

    expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');

    const revenue = await screen.findByRole('article', { name: '매출액' });
    expect(within(revenue).getByText('300조 8,709억')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: '2025년 핵심지표' }),
    ).toBeInTheDocument();

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/companies/00126380/metrics');
    expect(url).toContain('year=2025');
  });

  it('refetches when corpCode changes', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      return Promise.resolve(
        url.includes('/companies/A/')
          ? json(okBody('A', 1_0000_0000_0000))
          : json(okBody('B', 2_0000_0000_0000)),
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const { rerender } = render(<KeyMetricsSection corpCode="A" year={2025} />);
    expect(await screen.findByText('1조')).toBeInTheDocument();

    rerender(<KeyMetricsSection corpCode="B" year={2025} />);
    expect(await screen.findByText('2조')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('shows a not-found message for COMPANY_NOT_FOUND', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json(
          { success: false, error: { code: 'COMPANY_NOT_FOUND', message: 'x' } },
          404,
        ),
      ),
    );

    render(<KeyMetricsSection corpCode="000000" year={2025} />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '기업 정보를 찾을 수 없습니다',
    );
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('shows an error with a retry button that refetches', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(json(okBody('A', 5_0000_0000_0000)));
    vi.stubGlobal('fetch', fetchMock);

    render(<KeyMetricsSection corpCode="A" year={2025} />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '핵심지표를 불러오지 못했습니다',
    );

    await userEvent.click(screen.getByRole('button', { name: '다시 시도' }));

    await waitFor(() => expect(screen.getByText('5조')).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
