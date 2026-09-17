import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { KeyMetricsData } from '../../types/metrics';
import { GrowthKpiRow } from './GrowthKpiRow';
import { GrowthTrendCard } from './GrowthTrendCard';
import { ProfitabilityCard } from './ProfitabilityCard';
import { formatDelta } from '../../utils/formatDelta';
import { YoyCard } from './YoyCard';

const data: KeyMetricsData = {
  year: 2025,
  metrics: [
    { key: 'revenue', value: 300_900_000_000_000, prevValue: 295_800_000_000_000, changeRate: 1.7 },
    { key: 'operating_profit', value: 41_000_000_000_000, prevValue: 34_100_000_000_000, changeRate: 20.3 },
    { key: 'net_income', value: null, prevValue: null, changeRate: null },
    { key: 'employee_count', value: 125_000, prevValue: 121_900, changeRate: 2.5 },
    { key: 'average_salary', value: 124_000_000, prevValue: 118_990_000, changeRate: 4.2 },
    { key: 'average_tenure', value: 8.6, prevValue: 8.6, changeRate: 0 },
  ],
  profitability: { operatingMargin: 13.6, netMargin: null, debtRatio: 38.3 },
};

describe('GrowthKpiRow', () => {
  it('renders a card per available metric and folds missing ones into one note', () => {
    render(<GrowthKpiRow data={data} />);

    // 값이 없는 당기순이익은 카드가 아니라 아래 한 줄로 접힌다
    const cards = within(screen.getByRole('list', { name: '기준연도 핵심지표' })).getAllByRole('listitem');
    expect(cards).toHaveLength(5);
    expect(within(cards[0]).getByText('300.9조')).toBeInTheDocument();
    expect(within(cards[0]).getByText('2025년')).toBeInTheDocument();
    expect(within(cards[2]).getByText('125,000')).toBeInTheDocument();
    expect(within(cards[3]).getByText('1.2억')).toBeInTheDocument();
    expect(within(cards[4]).getByText('8.6')).toBeInTheDocument();
    expect(screen.queryByText('미제공')).not.toBeInTheDocument();
    expect(screen.getByText(/당기순이익 은\(는\) 이 기업의 공시 데이터가 없어/)).toBeInTheDocument();
  });

  it('shows one placeholder when every metric is missing', () => {
    render(
      <GrowthKpiRow
        data={{
          ...data,
          metrics: data.metrics.map((m) => ({ ...m, value: null, prevValue: null, changeRate: null })),
        }}
      />,
    );

    expect(screen.getByText('2025년 핵심지표가 미제공입니다')).toBeInTheDocument();
  });
});

describe('YoyCard', () => {
  it('shows signed rates with the absolute delta and 미제공 when the rate is unknown', () => {
    render(<YoyCard metrics={data.metrics} year={2025} />);

    expect(screen.getByText('(2024 → 2025)')).toBeInTheDocument();
    const revenue = within(screen.getByRole('listitem', { name: '매출 증가율' }));
    expect(revenue.getByText(/\+1\.7%/)).toBeInTheDocument();
    expect(revenue.getByText('+5.1조 원')).toBeInTheDocument();

    const employees = within(screen.getByRole('listitem', { name: '직원 증가율' }));
    expect(employees.getByText('+3,100명')).toBeInTheDocument();

    const salary = within(screen.getByRole('listitem', { name: '평균 급여 증가율' }));
    expect(salary.getByText('+501만 원')).toBeInTheDocument();
  });

  it('marks a missing rate as 미제공', () => {
    render(
      <YoyCard
        metrics={[{ key: 'revenue', value: 1, prevValue: null, changeRate: null }]}
        year={null}
      />,
    );
    expect(within(screen.getByRole('listitem', { name: '매출 증가율' })).getByText('미제공')).toBeInTheDocument();
  });

  it('formats deltas per unit', () => {
    expect(formatDelta('revenue', 5, 10)).toBe('-5 원');
    expect(formatDelta('employee_count', 100, 100)).toBe('0명');
  });
});

describe('ProfitabilityCard', () => {
  it('shows three ratios and 미제공 for the missing one', () => {
    render(<ProfitabilityCard profitability={data.profitability!} year={2025} />);

    const dl = screen.getByLabelText('수익성·안정성 비율');
    expect(within(dl).getByText('13.6%')).toBeInTheDocument();
    expect(within(dl).getByText('38.3%')).toBeInTheDocument();
    expect(within(dl).getByText('미제공')).toBeInTheDocument();
  });
});

describe('GrowthTrendCard', () => {
  const trend = {
    from: 2021,
    to: 2025,
    series: [
      {
        key: 'revenue' as const,
        points: [
          { year: 2021, value: 279_600_000_000_000, changeRate: null },
          { year: 2022, value: 302_200_000_000_000, changeRate: 8.1 },
          { year: 2023, value: null, changeRate: null },
          { year: 2024, value: 295_800_000_000_000, changeRate: null },
          { year: 2025, value: 300_900_000_000_000, changeRate: 1.7 },
        ],
      },
      {
        key: 'employee_count' as const,
        points: [{ year: 2025, value: 125_000, changeRate: 2.5 }],
      },
    ],
  };

  it('draws bars with rates, breaks at a missing year and switches metric without refetching', () => {
    render(<GrowthTrendCard corpCode="00126380" onRetry={() => {}} state={{ status: 'success', data: trend }} />);

    const chart = screen.getByRole('img', { name: /매출액 2021~2025년 변화 그래프/ });
    expect(within(chart).getAllByTestId('bar')).toHaveLength(4);
    expect(within(chart).getAllByTestId('rate-point')).toHaveLength(2);
    expect(within(chart).getByText('미제공')).toBeInTheDocument();
    expect(within(chart).getByText('+8.1%')).toBeInTheDocument();
    expect(screen.getByText('2021–2025 연간 · (단위: 원, %)')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: '직원 수' }));
    expect(screen.getByRole('heading', { name: '직원 수 추이' })).toBeInTheDocument();
  });

  it('labels the axis with whatever range the server returned', () => {
    render(
      <GrowthTrendCard
        corpCode="00126380"
        onRetry={() => {}}
        state={{
          status: 'success',
          data: {
            from: 2022,
            to: 2026,
            series: [{ key: 'revenue', points: [2022, 2023, 2024, 2025, 2026].map((year) => ({ year, value: null, changeRate: null })) }],
          },
        }}
      />,
    );

    const chart = screen.getByRole('img', { name: /매출액 2022~2026년 변화 그래프/ });
    expect(within(chart).getAllByText('미제공')).toHaveLength(5);
    expect(screen.getByText('2022–2026 연간 · (단위: 원, %)')).toBeInTheDocument();
  });

  it('shows no years while loading and explains when the selected metric has no series', () => {
    const { unmount } = render(
      <GrowthTrendCard corpCode="A" onRetry={() => {}} state={{ status: 'loading' }} />,
    );
    expect(screen.getByText('(단위: 원, %)')).toBeInTheDocument();
    unmount();

    render(
      <GrowthTrendCard
        corpCode="A"
        onRetry={() => {}}
        state={{ status: 'success', data: { from: 2021, to: 2025, series: [] } }}
      />,
    );
    expect(screen.getByText('매출액 추이 데이터가 없습니다')).toBeInTheDocument();
  });

  it('offers a retry on a server error', () => {
    const onRetry = vi.fn();
    render(
      <GrowthTrendCard
        corpCode="A"
        onRetry={onRetry}
        state={{ status: 'error', error: new ApiError(500, 'INTERNAL_ERROR', '서버') }}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

