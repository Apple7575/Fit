import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockFinancialTrendByCompany } from '../../mocks/financialTrend';
import { FinancialTrendSection } from './FinancialTrendSection';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

/** 명세 5번 응답 형태. mock 시계열을 그대로 series[] 로 담는다 */
const okBody = (corpCode: string) => ({
  success: true,
  data: {
    corpCode,
    from: 2021,
    to: 2025,
    series: mockFinancialTrendByCompany['00126380'],
  },
});

const stubFetch = (impl: (url: string) => Promise<Response>) => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => impl(String(input)));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
};

describe('FinancialTrendSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state, then draws the revenue chart from the API response', async () => {
    const fetchMock = stubFetch(() => Promise.resolve(json(okBody('00126380'))));

    render(<FinancialTrendSection corpCode="00126380" />);

    expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');
    expect(
      await screen.findByRole('img', { name: '매출액 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '2021년 279조 6,048억 원' }),
    ).toBeInTheDocument();

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/companies/00126380/metrics/timeseries');
    expect(url).toContain('from=2021');
    expect(url).toContain('to=2025');
  });

  it('keeps the metric selector usable and switches series without refetching', async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(() => Promise.resolve(json(okBody('A'))));

    render(<FinancialTrendSection corpCode="A" />);
    await screen.findByRole('img', { name: '매출액 2021~2025년 변화 그래프' });

    await user.click(screen.getByRole('radio', { name: '영업이익' }));

    expect(
      screen.getByRole('img', { name: '영업이익 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('refetches when corpCode changes', async () => {
    const fetchMock = stubFetch(() => Promise.resolve(json(okBody('x'))));

    const { rerender } = render(<FinancialTrendSection corpCode="A" />);
    await screen.findByRole('img');

    rerender(<FinancialTrendSection corpCode="B" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toContain('/companies/B/');
  });

  it('renders without error when the API omits a year and marks it 미제공', async () => {
    stubFetch(() =>
      Promise.resolve(
        json({
          success: true,
          data: {
            corpCode: 'A',
            from: 2021,
            to: 2025,
            series: [
              {
                key: 'revenue',
                // 2023 누락, 2024 는 null
                points: [
                  { year: 2021, value: 1_0000_0000_0000 },
                  { year: 2022, value: 2_0000_0000_0000 },
                  { year: 2024, value: null },
                  { year: 2025, value: 5_0000_0000_0000 },
                ],
              },
            ],
          },
        }),
      ),
    );

    render(<FinancialTrendSection corpCode="A" />);

    await screen.findByRole('img');
    const markers = screen.getAllByRole('button', { name: /^\d{4}년/ });
    expect(markers.map((m) => m.getAttribute('aria-label'))).toEqual([
      '2021년 1조 원',
      '2022년 2조 원',
      '2025년 5조 원',
    ]);
    const table = screen.getByRole('table');
    expect(table).toHaveTextContent('2023');
    expect(table).toHaveTextContent('미제공');
  });

  it('shows a not-found message for COMPANY_NOT_FOUND', async () => {
    stubFetch(() =>
      Promise.resolve(
        json(
          { success: false, error: { code: 'COMPANY_NOT_FOUND', message: 'x' } },
          404,
        ),
      ),
    );

    render(<FinancialTrendSection corpCode="000000" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '기업 정보를 찾을 수 없습니다',
    );
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('shows an error with a retry button that refetches', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(json(okBody('A')));
    vi.stubGlobal('fetch', fetchMock);

    render(<FinancialTrendSection corpCode="A" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '변화 그래프를 불러오지 못했습니다',
    );

    await user.click(screen.getByRole('button', { name: '다시 시도' }));

    expect(await screen.findByRole('img')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('shows an empty message when the selected metric is missing from the response', async () => {
    stubFetch(() =>
      Promise.resolve(
        json({
          success: true,
          data: { corpCode: 'A', from: 2021, to: 2025, series: [] },
        }),
      ),
    );

    render(<FinancialTrendSection corpCode="A" />);

    expect(
      await screen.findByText('매출액 추이 데이터가 없습니다'),
    ).toBeInTheDocument();
  });
});
