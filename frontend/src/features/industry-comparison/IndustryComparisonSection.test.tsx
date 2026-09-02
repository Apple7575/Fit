import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { toComparisonInsights } from './api';
import {
  ComparisonResult,
  IndustryComparisonSection,
} from './IndustryComparisonSection';
import type { IndustryComparison } from './types';
import type { ComparisonInsightsState } from './useComparisonInsights';

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

const okInsights: ComparisonInsightsState = {
  status: 'success',
  data: [{ title: '삼성전자는 규모가 가장 큽니다.', body: '매출 1위' }],
};

describe('ComparisonResult', () => {
  it('draws one bar per company with the target highlighted and first', () => {
    render(<ComparisonResult comparison={comparison} insights={okInsights} metricKey="revenue" />);

    const chart = screen.getByRole('img', { name: '매출 기업별 비교 차트' });
    const bars = within(chart).getAllByTestId('bar');
    expect(bars).toHaveLength(2); // DB하이텍 매출은 미제공
    expect(bars[0]).toHaveAttribute('data-highlight', 'true');
    expect(within(chart).getByText('302.2조')).toBeInTheDocument();
    expect(within(chart).getByText('미제공')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /매출 비교/ })).toHaveTextContent('(단위: 원)');
  });

  it('renders the insights and the full seven-metric table with the target row first', () => {
    render(<ComparisonResult comparison={comparison} insights={okInsights} metricKey="operating_margin" />);

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

  it('hides insights when empty and explains when there are no companies', () => {
    const { unmount } = render(
      <ComparisonResult comparison={comparison} insights={{ status: 'success', data: [] }} metricKey="revenue" />,
    );
    expect(screen.queryByRole('heading', { name: '핵심 인사이트' })).not.toBeInTheDocument();
    unmount();

    render(
      <ComparisonResult
        comparison={{ year: 2025, industry: null, metrics: [], companies: [] }}
        insights={{ status: 'error', error: new ApiError(404, 'X', 'x') }}
        metricKey="revenue"
      />,
    );
    expect(screen.getByText('비교할 동종 기업 정보가 없습니다')).toBeInTheDocument();
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
      { corpCode: '90000009', corpName: '리노공업' },
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

    expect(await screen.findByRole('img', { name: '매출 기업별 비교 차트' })).toBeInTheDocument();
    expect(
      screen.getAllByRole('radio').map((r) => r.parentElement?.textContent),
    ).toEqual(['매출', '매출 성장률', '영업이익', '영업이익률', '직원 수', '평균 급여', 'R&D 비율']);

    const urls = comparisonUrls(fetchMock);
    expect(urls).toHaveLength(1);
    expect(urls[0]).not.toContain('year=');
    expect(urls[0]).not.toContain('peers=');
    // peers 가 없으면 인사이트도 요청하지 않는다
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/insights'))).toBe(false);
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

    await screen.findByRole('img', { name: '매출 기업별 비교 차트' });
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
    await screen.findByRole('img', { name: '매출 기업별 비교 차트' });

    // 4개가 찼으므로 검색은 비활성
    expect(screen.getByLabelText('비교할 기업명')).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'DB하이텍 제거' }));
    await waitFor(() => expect(comparisonUrls(fetchMock)).toHaveLength(2));
    expect(comparisonUrls(fetchMock)[1]).toContain('peers=00164779%2C00401731');

    fireEvent.change(screen.getByLabelText('비교할 기업명'), { target: { value: 'LG디스' } });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));
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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json({ success: false, error: { code: 'INTERNAL_ERROR', message: '서버 오류' } }, 500),
      )
      .mockResolvedValueOnce(json({ success: true, data: comparison }));
    vi.stubGlobal('fetch', fetchMock);

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(await screen.findByRole('alert')).toHaveTextContent('산업 비교를 불러오지 못했습니다');
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(await screen.findByRole('img', { name: '매출 기업별 비교 차트' })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('drops metric keys the frontend does not know', async () => {
    stubByUrl(() =>
      json({
        success: true,
        data: { ...comparison, metrics: [...comparison.metrics, 'unknown_metric'] },
      }),
    );

    render(<IndustryComparisonSection corpCode="00126380" />);

    await screen.findByRole('img', { name: '매출 기업별 비교 차트' });
    expect(screen.getAllByRole('radio')).toHaveLength(7);
  });
});
