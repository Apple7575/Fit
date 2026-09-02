import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  IndustryComparisonSection,
  IndustryComparisonView,
} from './IndustryComparisonSection';
import type { IndustryComparison } from './types';

/** 명세 5번(v2) 응답 형태 — 서버 기본 7종 중 프론트가 아는 6종만 metrics 에 실린다 */
const comparison: IndustryComparison = {
  year: 2025,
  industry: {
    code: '26',
    name: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
    companyCount: 42,
  },
  metrics: [
    'revenue',
    'revenue_growth',
    'operating_profit',
    'operating_margin',
    'employee_count',
    'average_salary',
  ],
  companies: [
    {
      corpCode: '00126380',
      corpName: '삼성전자',
      isTarget: true,
      values: {
        revenue: 300_870_903_000_000,
        revenue_growth: 1.7,
        operating_profit: 6_566_976_000_000,
        operating_margin: 2.2,
        employee_count: 124_804,
        average_salary: 130_000_000,
      },
    },
    {
      corpCode: '00164779',
      corpName: 'SK하이닉스',
      isTarget: false,
      values: {
        revenue: 66_193_000_000_000,
        revenue_growth: 17.1,
        operating_profit: 23_467_000_000_000,
        operating_margin: 35.5,
        employee_count: 31_000,
        average_salary: 120_000_000,
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
      },
    },
  ],
};

const renderView = (data: IndustryComparison = comparison) =>
  render(<IndustryComparisonView comparison={data} />);

/** 막대 목록(ul 첫 번째)의 행 */
const barList = () => screen.getAllByRole('list')[0];

const peerRow = (corpName: string) => {
  const row = within(barList()).getByText(corpName).closest('li');
  if (!row) {
    throw new Error(`${corpName} 행을 찾지 못했습니다`);
  }
  return within(row);
};

const peerNames = () =>
  within(barList())
    .getAllByRole('listitem')
    .map((row) => row.querySelector('span')?.textContent);

describe('IndustryComparisonView', () => {
  it('describes the industry, how many peers are shown, the metric and the year', () => {
    renderView();

    expect(screen.getByText(/전자 부품, 컴퓨터/)).toBeInTheDocument();
    expect(screen.getByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액 기준/)).toBeInTheDocument();
  });

  it('offers all ten comparison metrics and marks the ones the API does not provide', () => {
    renderView();

    const radios = screen
      .getAllByRole('radio')
      .map((r) => r.parentElement?.textContent);
    expect(radios.slice(0, 10)).toEqual([
      '매출액',
      '매출 성장률',
      '영업이익',
      '영업이익률',
      '순이익(미제공)',
      '부채비율(미제공)',
      '직원 수',
      '직원 증가율(미제공)',
      '1인 평균 급여',
      '평균 근속(미제공)',
    ]);
    expect(radios.slice(10)).toEqual(['값이 큰 순', '값이 작은 순']);
  });

  it('shows every company as 미제공 with a note when an unsupported metric is chosen', () => {
    renderView();

    fireEvent.click(screen.getByRole('radio', { name: /부채비율/ }));

    expect(screen.getByRole('note')).toHaveTextContent('아직 비교 API에서 제공되지 않아');
    expect(peerRow('삼성전자').getByText('미제공')).toBeInTheDocument();
    expect(peerRow('SK하이닉스').getByText('미제공')).toBeInTheDocument();
  });

  it('compares ratio metrics in percent', () => {
    renderView();

    fireEvent.click(screen.getByRole('radio', { name: '영업이익률' }));
    expect(peerRow('SK하이닉스').getByText('35.5')).toBeInTheDocument();
    expect(peerRow('SK하이닉스').getByText('%')).toBeInTheDocument();
    expect(peerRow('DB하이텍').getByText('-8.5')).toHaveClass('text-rose-600');
  });

  it('lists every company with the value of the selected metric and its unit', () => {
    renderView();

    expect(within(barList()).getAllByRole('listitem')).toHaveLength(3);
    const samsung = peerRow('삼성전자');
    expect(samsung.getByText('300조 8,709억')).toBeInTheDocument();
    expect(samsung.getByText('원')).toBeInTheDocument();
  });

  it('marks the target company using isTarget from the response', () => {
    renderView();

    expect(peerRow('삼성전자').getByText('조회 기업')).toBeInTheDocument();
    expect(
      peerRow('SK하이닉스').queryByText('조회 기업'),
    ).not.toBeInTheDocument();
  });

  it('shows 미제공 instead of 0 when a value is missing', () => {
    renderView();

    expect(peerRow('DB하이텍').getByText('미제공')).toBeInTheDocument();
  });

  it('switches the compared metric and its unit without dropping companies', () => {
    renderView();

    fireEvent.click(screen.getByRole('radio', { name: '직원 수' }));

    expect(screen.getByText(/2025년 직원 수 기준/)).toBeInTheDocument();
    expect(within(barList()).getAllByRole('listitem')).toHaveLength(3);
    const samsung = peerRow('삼성전자');
    expect(samsung.getByText('124,804')).toBeInTheDocument();
    expect(samsung.getByText('명')).toBeInTheDocument();
  });

  it('reverses the order when a different sort is chosen, keeping missing values last', () => {
    renderView();

    expect(peerNames()).toEqual(['삼성전자', 'SK하이닉스', 'DB하이텍']);

    fireEvent.click(screen.getByRole('radio', { name: '값이 작은 순' }));

    expect(peerNames()).toEqual(['SK하이닉스', '삼성전자', 'DB하이텍']);
  });

  it('renders the full table with the target row first and missing cells as 미제공', () => {
    renderView();

    const table = screen.getByRole('table', { name: '기업별 비교 지표 전체 표' });
    const rows = within(table).getAllByRole('row');
    // header + 3 companies
    expect(rows).toHaveLength(4);
    expect(rows[1]).toHaveTextContent('삼성전자');
    expect(rows[1]).toHaveTextContent('조회 기업');
    expect(within(rows[1]).getAllByText('미제공')).toHaveLength(4); // 순이익·부채비율·직원 증가율·평균 근속
    expect(within(table).getAllByRole('columnheader')).toHaveLength(11);
  });

  it('explains when there are no peers and keeps the year visible', () => {
    renderView({ year: 2025, industry: null, metrics: [], companies: [] });

    expect(
      screen.getByText('비교할 동종 기업 정보가 없습니다'),
    ).toBeInTheDocument();
    expect(screen.getByText(/산업 정보 없음/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액 기준/)).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
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
    industry: { code: '26', name: '전자 부품' },
    companies: [
      { corpCode: '00126380', corpName: '삼성전자' },
      { corpCode: '00401731', corpName: 'LG전자' },
      { corpCode: '00164779', corpName: 'SK하이닉스' },
      { corpCode: '00113058', corpName: 'DB하이텍' },
      { corpCode: '90000009', corpName: '리노공업' },
    ],
  },
};

/** URL 로 후보 API 와 비교 API 를 구분한다 */
const stubByUrl = (
  comparisonImpl: () => Response = () => json({ success: true, data: comparison }),
) => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/industries/')) {
      return Promise.resolve(json(candidatesBody));
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

  it('fetches the comparison for the company without peers when no industry is known', async () => {
    const fetchMock = stubByUrl();

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');
    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();

    const urls = comparisonUrls(fetchMock);
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain('/api/companies/00126380/industry-comparison');
    // 기준연도는 서버가 정한다 — 프론트는 year 를 보내지 않는다
    expect(urls[0]).not.toContain('year=');
    expect(urls[0]).not.toContain('peers=');
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('/api/industries/'))).toBe(false);
  });

  it('loads same-industry candidates, preselects the top three and sends them as peers', async () => {
    const fetchMock = stubByUrl();

    render(<IndustryComparisonSection corpCode="00126380" industryCode="26" />);

    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();

    const candidates = screen.getByRole('group', { name: /비교 기업 선택/ });
    const checked = within(candidates)
      .getAllByRole('checkbox')
      .filter((box) => (box as HTMLInputElement).checked)
      .map((box) => (box as HTMLInputElement).value);
    // 대상 기업(삼성전자)은 후보에서 빠지고 매출순 상위 3곳이 선택된다
    expect(checked).toEqual(['00401731', '00164779', '00113058']);
    expect(within(candidates).queryByLabelText('삼성전자')).not.toBeInTheDocument();

    const urls = comparisonUrls(fetchMock);
    expect(urls).toHaveLength(1); // 후보를 기다렸다가 한 번만 조회
    // peers 는 정렬해서 보낸다 (순서만 다른 같은 선택으로 재조회하지 않기 위해)
    expect(urls[0]).toContain('peers=00113058%2C00164779%2C00401731');
  });

  it('refetches with the new peers when the selection changes and caps at three', async () => {
    const fetchMock = stubByUrl();

    render(<IndustryComparisonSection corpCode="00126380" industryCode="26" />);
    await screen.findByText(/동종 42개사 중 3개/);

    const fourth = screen.getByRole('checkbox', { name: '리노공업' });
    expect(fourth).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', { name: 'DB하이텍' }));
    await waitFor(() => expect(fourth).toBeEnabled());
    fireEvent.click(fourth);

    await waitFor(() => expect(comparisonUrls(fetchMock)).toHaveLength(3));
    expect(comparisonUrls(fetchMock)[2]).toContain(
      'peers=00164779%2C00401731%2C90000009',
    );
  });

  it('shows a not-found message for COMPANY_NOT_FOUND', async () => {
    stubByUrl(() =>
      json(
        { success: false, error: { code: 'COMPANY_NOT_FOUND', message: 'x' } },
        404,
      ),
    );

    render(<IndustryComparisonSection corpCode="99999999" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '기업 정보를 찾을 수 없습니다',
    );
    expect(
      screen.queryByRole('button', { name: '다시 시도' }),
    ).not.toBeInTheDocument();
  });

  it('offers a retry that refetches after a server error', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json(
          { success: false, error: { code: 'INTERNAL_ERROR', message: '서버 오류' } },
          500,
        ),
      )
      .mockResolvedValueOnce(json({ success: true, data: comparison }));
    vi.stubGlobal('fetch', fetchMock);

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '산업 비교를 불러오지 못했습니다',
    );

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));

    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('drops metric keys the frontend does not know', async () => {
    stubByUrl(() =>
      json({
        success: true,
        data: {
          ...comparison,
          metrics: [...comparison.metrics, 'rd_ratio', 'unknown_metric'],
        },
      }),
    );

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    // 10 지표 + 정렬 2 — 모르는 키는 선택지에 끼지 않는다
    expect(screen.getAllByRole('radio')).toHaveLength(12);
  });
});
