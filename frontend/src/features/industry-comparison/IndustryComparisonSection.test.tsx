import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  IndustryComparisonSection,
  IndustryComparisonView,
} from './IndustryComparisonSection';
import type { IndustryComparison } from './types';

/** 명세 5번 응답 형태 */
const comparison: IndustryComparison = {
  year: 2025,
  industry: {
    code: '26',
    name: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
    companyCount: 42,
  },
  metrics: ['revenue', 'operating_profit', 'employee_count', 'avg_salary', 'avg_tenure', 'rd_ratio'],
  companies: [
    {
      corpCode: '00126380',
      corpName: '삼성전자',
      isTarget: true,
      values: {
        revenue: 300_870_903_000_000,
        operating_profit: 6_566_976_000_000,
        employee_count: 124_804,
        avg_salary: 130_000_000,
        avg_tenure: 12.4,
        rd_ratio: 8.3,
      },
    },
    {
      corpCode: '00164779',
      corpName: 'SK하이닉스',
      isTarget: false,
      values: {
        revenue: 66_193_000_000_000,
        operating_profit: 23_467_000_000_000,
        employee_count: 31_000,
        avg_salary: 120_000_000,
        avg_tenure: 11.2,
        rd_ratio: 6.1,
      },
    },
    {
      corpCode: '00113058',
      corpName: 'DB하이텍',
      isTarget: false,
      values: {
        revenue: null,
        operating_profit: -97_000_000_000,
        employee_count: 2_100,
        avg_salary: null,
        avg_tenure: null,
        rd_ratio: 3.4,
      },
    },
  ],
};

const renderSection = (data: IndustryComparison = comparison) =>
  render(<IndustryComparisonView comparison={data} />);

const peerRow = (corpName: string) => {
  const row = screen.getByText(corpName).closest('li');
  if (!row) {
    throw new Error(`${corpName} 행을 찾지 못했습니다`);
  }
  return within(row);
};

const peerNames = () =>
  screen
    .getAllByRole('listitem')
    .map((row) => row.querySelector('span')?.textContent);

describe('IndustryComparisonView', () => {
  it('describes the industry, how many peers are shown, the metric and the year', () => {
    renderSection();

    expect(
      screen.getByRole('heading', { level: 2, name: '같은 산업 비교' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/전자 부품, 컴퓨터/)).toBeInTheDocument();
    expect(screen.getByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액 기준/)).toBeInTheDocument();
  });

  it('offers all six metrics listed in the response', () => {
    renderSection();

    expect(
      screen.getAllByRole('radio').map((r) => r.parentElement?.textContent),
    ).toEqual([
      '매출액',
      '영업이익',
      '직원 수',
      '1인 평균 급여',
      '평균 근속',
      'R&D / 매출',
      '값이 큰 순',
      '값이 작은 순',
    ]);
  });

  it('compares tenure in years and R&D ratio in percent', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '평균 근속' }));
    expect(peerRow('삼성전자').getByText('12.4')).toBeInTheDocument();
    expect(peerRow('삼성전자').getByText('년')).toBeInTheDocument();
    expect(peerRow('DB하이텍').getByText('미제공')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: 'R&D / 매출' }));
    expect(peerRow('DB하이텍').getByText('3.4')).toBeInTheDocument();
    expect(peerRow('DB하이텍').getByText('%')).toBeInTheDocument();
  });

  it('lists every company with the value of the selected metric and its unit', () => {
    renderSection();

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    const samsung = peerRow('삼성전자');
    expect(samsung.getByText('300조 8,709억')).toBeInTheDocument();
    expect(samsung.getByText('원')).toBeInTheDocument();
  });

  it('marks the target company using isTarget from the response', () => {
    renderSection();

    expect(peerRow('삼성전자').getByText('조회 기업')).toBeInTheDocument();
    expect(
      peerRow('SK하이닉스').queryByText('조회 기업'),
    ).not.toBeInTheDocument();
  });

  it('shows 미제공 instead of 0 when a value is missing', () => {
    renderSection();

    expect(peerRow('DB하이텍').getByText('미제공')).toBeInTheDocument();
  });

  it('switches the compared metric and its unit without dropping companies', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '직원 수' }));

    expect(screen.getByText(/2025년 직원 수 기준/)).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    const samsung = peerRow('삼성전자');
    expect(samsung.getByText('124,804')).toBeInTheDocument();
    expect(samsung.getByText('명')).toBeInTheDocument();
  });

  it('shows negative values as a loss', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '영업이익' }));

    expect(peerRow('DB하이텍').getByText('-970억')).toHaveClass('text-rose-600');
  });

  it('reverses the order when a different sort is chosen, keeping missing values last', () => {
    renderSection();

    expect(peerNames()).toEqual(['삼성전자', 'SK하이닉스', 'DB하이텍']);

    fireEvent.click(screen.getByRole('radio', { name: '값이 작은 순' }));

    expect(peerNames()).toEqual(['SK하이닉스', '삼성전자', 'DB하이텍']);
  });

  it('starts sorted from the largest value', () => {
    renderSection();

    expect(screen.getByRole('radio', { name: '값이 큰 순' })).toBeChecked();
  });

  it('explains when there are no peers and keeps the year visible', () => {
    renderSection({ year: 2025, industry: null, metrics: [], companies: [] });

    expect(
      screen.getByText('비교할 동종 기업 정보가 없습니다'),
    ).toBeInTheDocument();
    expect(screen.getByText(/산업 정보 없음/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액 기준/)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('IndustryComparisonSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches the comparison for the company and renders it', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(json({ success: true, data: comparison }));
    vi.stubGlobal('fetch', fetchMock);

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(screen.getByRole('status')).toHaveTextContent('불러오는 중');
    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/companies/00126380/industry-comparison');
    expect(url).toContain('year=2025');
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
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json({
          success: true,
          data: {
            ...comparison,
            metrics: [...comparison.metrics, 'unknown_metric'],
          },
        }),
      ),
    );

    render(<IndustryComparisonSection corpCode="00126380" />);

    expect(await screen.findByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(8);
  });
});
