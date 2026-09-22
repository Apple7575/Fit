import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { fetchComparisonTrends, toComparisonInsights } from './api';
import {
  ComparisonResult,
  IndustryComparisonSection,
} from './IndustryComparisonSection';
import type { IndustryComparison } from './types';
import type { ComparisonInsightsState } from './useComparisonInsights';
import type { ComparisonTrendsState } from './useComparisonTrends';

/** 명세 5번(v2) 응답 형태 — 서버 기본 7종 */
const comparison: IndustryComparison = {
  year: 2025,
  industry: { code: '26', name: '전기·전자', companyCount: 42 },
  metrics: [
    'revenue',
    'revenue_growth',
    'operating_profit',
    'operating_margin',
    'employee_count',
    'average_salary',
    'rd_ratio',
  ],
  companies: [
    {
      corpCode: '00164779',
      corpName: 'SK하이닉스',
      isTarget: false,
      values: {
        revenue: 66_200_000_000_000,
        revenue_growth: 17.1,
        operating_profit: 21_800_000_000_000,
        operating_margin: 32.8,
        employee_count: 32_947,
        average_salary: 118_000_000,
        rd_ratio: 14.0,
      },
    },
    {
      corpCode: '00126380',
      corpName: '삼성전자',
      isTarget: true,
      values: {
        revenue: 302_200_000_000_000,
        revenue_growth: 5.4,
        operating_profit: 32_700_000_000_000,
        operating_margin: 10.8,
        employee_count: 129_300,
        average_salary: 124_000_000,
        rd_ratio: 8.1,
      },
    },
    {
      corpCode: '00113058',
      corpName: 'DB하이텍',
      isTarget: false,
      values: {
        revenue: null,
        revenue_growth: null,
        operating_profit: -97_000_000_000,
        operating_margin: -8.5,
        employee_count: 2_100,
        average_salary: null,
        rd_ratio: 9.3,
      },
    },
  ],
};

const yearRow = (revenue: number | null, op: number | null) => ({
  revenue,
  operating_profit: op,
  operating_margin: revenue && op !== null ? Math.round((op / revenue) * 1000) / 10 : null,
});
const YEARS = [2021, 2022, 2023, 2024, 2025];
const trendsOk: ComparisonTrendsState = {
  status: 'success',
  data: [
    {
      corpCode: '00126380',
      corpName: '삼성전자',
      years: YEARS,
      values: {
        2021: yearRow(279_600e9, 51_600e9),
        2022: yearRow(302_200e9, 43_400e9),
        2023: yearRow(258_900e9, 6_600e9),
        2024: yearRow(300_900e9, 32_700e9),
        2025: yearRow(302_200e9, 32_700e9),
      },
    },
    {
      corpCode: '00164779',
      corpName: 'SK하이닉스',
      years: YEARS,
      values: {
        2021: yearRow(42_900e9, 12_400e9),
        2022: yearRow(44_600e9, 6_800e9),
        2023: yearRow(null, null),
        2024: yearRow(66_200e9, 23_500e9),
        2025: yearRow(77_600e9, 25_500e9),
      },
    },
  ],
};

const okInsights: ComparisonInsightsState = {
  status: 'success',
  data: [{ title: '삼성전자는 규모가 가장 큽니다.', body: '매출 1위' }],
};

describe('ComparisonResult', () => {
  it('draws one coloured line per company over five years and bridges missing years', () => {
    render(
      <ComparisonResult comparison={comparison} insights={okInsights} metricKey="revenue" trends={trendsOk} />,
    );

    const chart = screen.getByRole('img', { name: '매출 기업별 5개년 비교 차트' });
    const lines = within(chart).getAllByTestId('line-series');
    expect(lines).toHaveLength(2);
    expect(lines[0]).toHaveAttribute('data-series', '삼성전자');
    // 삼성전자 5점, SK하이닉스 2023 결측 → 4점
    expect(within(lines[0]).getAllByTestId('line-point')).toHaveLength(5);
    expect(within(lines[1]).getAllByTestId('line-point')).toHaveLength(4);
    /*
     * 값이 빠진 해에서 선을 끊지 않는다. 끊기면 그래프가 고장 난 것처럼 보였다.
     * 대신 건너뛴 구간만 점선으로 구분한다 — 실선 두 조각 + 점선 한 조각.
     */
    expect(within(lines[1]).getAllByTestId('line-bridge')).toHaveLength(1);
    expect(lines[1].querySelectorAll('polyline')).toHaveLength(3);
    // 값이 다 있는 쪽에는 점선이 없다
    expect(within(lines[0]).queryByTestId('line-bridge')).not.toBeInTheDocument();
    expect(screen.getByText('값이 없는 해를 건너뛴 구간')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /매출 5개년 비교/ })).toHaveTextContent('단위: 원');
    const legend = within(screen.getByRole('list', { name: '범례' }));
    expect(legend.getByText('삼성전자')).toBeInTheDocument();
    expect(legend.getByText('SK하이닉스')).toBeInTheDocument();
  });

  it('labels the chart with the range the trends came back with', () => {
    const shifted: ComparisonTrendsState = {
      status: 'success',
      data: [
        {
          corpCode: '00126380',
          corpName: '삼성전자',
          years: [2022, 2023, 2024, 2025, 2026],
          values: { 2022: yearRow(1, 1), 2023: yearRow(2, 1), 2024: yearRow(3, 1), 2025: yearRow(4, 1), 2026: yearRow(5, 1) },
        },
      ],
    };
    render(
      <ComparisonResult comparison={comparison} insights={okInsights} metricKey="revenue" trends={shifted} />,
    );

    expect(screen.getByRole('heading', { name: /매출 5개년 비교/ })).toHaveTextContent('2022–2026');
    const chart = screen.getByRole('img', { name: '매출 기업별 5개년 비교 차트' });
    expect(within(chart).getAllByTestId('line-point')).toHaveLength(5);
  });

  it('shows a loading placeholder and an error notice for the trend chart only', () => {
    const { unmount } = render(
      <ComparisonResult comparison={comparison} insights={okInsights} metricKey="revenue" trends={{ status: 'loading' }} />,
    );
    expect(screen.getByRole('status')).toHaveTextContent('5개년 지표를 불러오는 중');
    // 구간은 응답에서만 오므로 도착 전에는 연도를 표시하지 않는다
    expect(screen.getByRole('heading', { name: /매출 5개년 비교/ })).toHaveTextContent('(단위: 원)');
    expect(screen.getByRole('table', { name: '기업별 비교 지표 전체 표' })).toBeInTheDocument();
    unmount();

    const onRetry = vi.fn();
    render(
      <ComparisonResult
        comparison={comparison}
        insights={okInsights}
        metricKey="revenue"
        onRetryTrends={onRetry}
        trends={{ status: 'error', error: new ApiError(500, 'INTERNAL_ERROR', '서버') }}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders the insights and the full seven-metric table with the target row first', () => {
    render(
      <ComparisonResult comparison={comparison} insights={okInsights} metricKey="operating_margin" trends={trendsOk} />,
    );

    expect(screen.getByRole('heading', { name: '핵심 인사이트' })).toBeInTheDocument();
    expect(screen.getByText('삼성전자는 규모가 가장 큽니다.')).toBeInTheDocument();

    const table = screen.getByRole('table', { name: '기업별 비교 지표 전체 표' });
    const rows = within(table).getAllByRole('row');
    expect(rows).toHaveLength(4);
    expect(rows[1]).toHaveTextContent('삼성전자');
    expect(rows[1]).toHaveTextContent('조회 기업');
    expect(within(table).getAllByRole('columnheader')).toHaveLength(8);
    expect(within(rows[3]).getAllByText('미제공')).toHaveLength(3);
    expect(within(rows[3]).getByText('-970억')).toHaveClass('text-rose-600');
    expect(screen.getByText(/기준 2025년/)).toBeInTheDocument();
  });

  it('explains insights when empty and when there are no companies', () => {
    const { unmount } = render(
      <ComparisonResult
        comparison={comparison}
        insights={{ status: 'success', data: [] }}
        metricKey="revenue"
        trends={trendsOk}
      />,
    );
    // 비어도 카드는 자리를 지키고 왜 없는지 알려 준다
    expect(screen.getByRole('heading', { name: '핵심 인사이트' })).toBeInTheDocument();
    expect(screen.getByText(/비교 인사이트는 아직 준비 중/)).toBeInTheDocument();
    unmount();

    render(
      <ComparisonResult
        comparison={{ year: 2025, industry: null, metrics: [], companies: [] }}
        insights={{ status: 'error', error: new ApiError(404, 'X', 'x') }}
        metricKey="revenue"
        trends={trendsOk}
      />,
    );
    expect(screen.getByText('비교할 동종 기업 정보가 없습니다')).toBeInTheDocument();
  });
});

describe('fetchComparisonTrends', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('puts a 404 company on the range the other companies came back with', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).includes('/companies/GONE/')
            ? json({ success: false, error: { code: 'COMPANY_NOT_FOUND', message: 'x' } }, 404)
            : json({
                success: true,
                data: {
                  range: { from: 2022, to: 2026 },
                  series: [{ key: 'revenue', points: [{ year: 2026, value: 1 }] }],
                },
              }),
        ),
      ),
    );

    const trends = await fetchComparisonTrends([
      { corpCode: 'GONE', corpName: '없는기업' },
      { corpCode: 'A', corpName: '에이' },
    ]);

    expect(trends[1].years).toEqual([2022, 2023, 2024, 2025, 2026]);
    expect(trends[0].years).toEqual([2022, 2023, 2024, 2025, 2026]);
    expect(Object.values(trends[0].values[2026]).every((v) => v === null)).toBe(true);
  });
});

describe('toComparisonInsights', () => {
  it('promotes body-only items to a title and drops empty ones', () => {
    expect(
      toComparisonInsights({
        insights: [{ title: 'A', body: 'a' }, { title: null, body: 'only body' }, { title: '', body: '' }],
      }),
    ).toEqual([
      { title: 'A', body: 'a' },
      { title: 'only body', body: null },
    ]);
  });
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const candidatesBody = {
  success: true,
  data: {
    industry: { code: '26', name: '전기·전자' },
    companies: [
      { corpCode: '00126380', corpName: '삼성전자' },
      { corpCode: '00164779', corpName: 'SK하이닉스' },
      { corpCode: '00401731', corpName: 'LG전자' },
      { corpCode: '00113058', corpName: 'DB하이텍' },
      { corpCode: '00369657', corpName: '리노공업' },
    ],
  },
};

const searchBody = {
  success: true,
  data: {
    items: [
      { corpCode: '90000011', corpName: 'LG디스플레이', stockCode: '034220', industryCode: '26', industryName: '전기·전자' },
    ],
    total: 1,
  },
};

/** URL 로 후보·검색·인사이트·비교 API 를 구분한다 */
const stubByUrl = (
  comparisonImpl: () => Response = () => json({ success: true, data: comparison }),
) => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/industries/')) return Promise.resolve(json(candidatesBody));
    if (url.includes('/api/companies?')) return Promise.resolve(json(searchBody));
    if (url.includes('/insights')) {
      return Promise.resolve(json({ success: true, data: { section: 'comparison', insights: [] } }));
    }
    if (url.includes('/metrics/timeseries')) {
      return Promise.resolve(
        json({
          success: true,
          data: {
            range: { from: 2021, to: 2025 },
            series: [{ key: 'revenue', points: [{ year: 2025, value: 1_0000_0000_0000 }] }],
          },
        }),
      );
    }
    return Promise.resolve(comparisonImpl());
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
};

const comparisonUrls = (fetchMock: ReturnType<typeof vi.fn>) =>
  fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes('/industry-comparison'));

describe('IndustryComparisonSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('offers the seven API metrics and fetches without peers when no industry is known', async () => {
    const fetchMock = stubByUrl();

    render(<IndustryComparisonSection corpCode="00126380" corpName="삼성전자" />);

    expect(await screen.findByRole('img', { name: '매출 기업별 5개년 비교 차트' })).toBeInTheDocument();
    expect(
      screen.getAllByRole('radio').map((r) => r.parentElement?.textContent),
    ).toEqual(['매출', '매출 성장률', '영업이익', '영업이익률', '직원 수', '평균 급여', 'R&D 비율']);

    const urls = comparisonUrls(fetchMock);
    expect(urls).toHaveLength(1);
    expect(urls[0]).not.toContain('year=');
    expect(urls[0]).not.toContain('peers=');
    // peers 가 없으면 인사이트도 요청하지 않는다
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/insights'))).toBe(false);
    // 5개년 시계열도 구간을 박지 않고 서버 기준연도를 따른다 (비교 조회와 같은 해)
    const trendUrls = fetchMock.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/metrics/timeseries'));
    expect(trendUrls).toHaveLength(1);
    expect(trendUrls[0]).toContain('keys=revenue%2Coperating_profit%2Cemployee_count%2Caverage_salary%2Crd_ratio');
    expect(trendUrls[0]).not.toContain('from=');
    expect(trendUrls[0]).not.toContain('to=');
  });

  it('preselects the top three same-industry companies and requests insights for them', async () => {
    const fetchMock = stubByUrl();

    render(
      <IndustryComparisonSection
        corpCode="00126380"
        corpName="삼성전자"
        industryCode="26"
        industryName="전기·전자"
      />,
    );

    await screen.findByRole('img', { name: '매출 기업별 5개년 비교 차트' });
    const chips = within(screen.getByRole('list', { name: '선택된 비교 기업' })).getAllByRole('listitem');
    expect(chips.map((c) => c.textContent)).toEqual([
      '삼성전자조회 기업',
      'SK하이닉스×',
      'LG전자×',
      'DB하이텍×',
    ]);

    const urls = comparisonUrls(fetchMock);
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain('peers=00113058%2C00164779%2C00401731');
    const insightUrl = fetchMock.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/insights'));
    expect(insightUrl).toContain('section=comparison');
    expect(insightUrl).toContain('peers=');
  });

  it('adds a company found by name search and removes one with the × button', async () => {
    const fetchMock = stubByUrl();

    render(
      <IndustryComparisonSection corpCode="00126380" corpName="삼성전자" industryCode="26" />,
    );
    await screen.findByRole('img', { name: '매출 기업별 5개년 비교 차트' });

    // 4개가 찼으므로 검색은 비활성
    expect(screen.getByLabelText('비교할 기업명')).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'DB하이텍 제거' }));
    await waitFor(() => expect(comparisonUrls(fetchMock)).toHaveLength(2));
    expect(comparisonUrls(fetchMock)[1]).toContain('peers=00164779%2C00401731');

    // 기업 분석 검색칸과 같다 — 엔터를 치지 않아도 치는 대로 따라온다
    fireEvent.change(screen.getByLabelText('비교할 기업명'), { target: { value: 'LG디스' } });
    fireEvent.click(await screen.findByRole('button', { name: /LG디스플레이/ }));

    await waitFor(() => expect(comparisonUrls(fetchMock)).toHaveLength(3));
    expect(comparisonUrls(fetchMock)[2]).toContain('peers=00164779%2C00401731%2C90000011');
    expect(screen.getByRole('button', { name: 'LG디스플레이 제거' })).toBeInTheDocument();
  });

  it('shows a not-found message for COMPANY_NOT_FOUND', async () => {
    stubByUrl(() =>
      json({ success: false, error: { code: 'COMPANY_NOT_FOUND', message: 'x' } }, 404),
    );

    render(<IndustryComparisonSection corpCode="99999999" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('기업 정보를 찾을 수 없습니다');
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument();
  });

  it('offers a retry that refetches after a server error', async () => {
    let comparisonCalls = 0;
    const fetchMock = stubByUrl(() => {
      comparisonCalls += 1;
      return comparisonCalls === 1
        ? json({ success: false, error: { code: 'INTERNAL_ERROR', message: '서버 오류' } }, 500)
        : json({ success: true, data: comparison });
    });

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('산업 비교를 불러오지 못했습니다');
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(await screen.findByRole('img', { name: '매출 기업별 5개년 비교 차트' })).toBeInTheDocument();
    expect(comparisonUrls(fetchMock)).toHaveLength(2);
  });

  it('drops metric keys the frontend does not know', async () => {
    stubByUrl(() =>
      json({
        success: true,
        data: { ...comparison, metrics: [...comparison.metrics, 'unknown_metric'] },
      }),
    );

    render(<IndustryComparisonSection corpCode="00126380" />);

    await screen.findByRole('img', { name: '매출 기업별 5개년 비교 차트' });
    expect(screen.getAllByRole('radio')).toHaveLength(7);
  });
});
