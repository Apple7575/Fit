import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IndustryComparisonSection } from './IndustryComparisonSection';
import type { IndustryComparison } from './types';

/** 명세 5번 응답 형태 */
const comparison: IndustryComparison = {
  year: 2025,
  industry: {
    code: '26',
    name: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
    companyCount: 42,
  },
  metrics: ['revenue', 'operating_profit', 'employee_count', 'avg_salary'],
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
      },
    },
  ],
};

const renderSection = (data: IndustryComparison = comparison) =>
  render(<IndustryComparisonSection comparison={data} />);

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

describe('IndustryComparisonSection', () => {
  it('describes the industry, how many peers are shown, the metric and the year', () => {
    renderSection();

    expect(
      screen.getByRole('heading', { level: 2, name: '같은 산업 비교' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/전자 부품, 컴퓨터/)).toBeInTheDocument();
    expect(screen.getByText(/동종 42개사 중 3개/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액 기준/)).toBeInTheDocument();
  });

  it('offers only the four comparison metrics from the response', () => {
    renderSection();

    expect(
      screen.getAllByRole('radio').map((r) => r.parentElement?.textContent),
    ).toEqual([
      '매출액',
      '영업이익',
      '직원 수',
      '1인 평균 급여',
      '값이 큰 순',
      '값이 작은 순',
    ]);
    expect(
      screen.queryByRole('radio', { name: '평균 근속' }),
    ).not.toBeInTheDocument();
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
