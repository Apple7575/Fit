import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
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
  it('renders six compact KPI cards with the year and 미제공 for missing values', () => {
    render(<GrowthKpiRow data={data} />);

    const cards = within(screen.getByRole('list', { name: '기준연도 핵심지표' })).getAllByRole('listitem');
    expect(cards).toHaveLength(6);
    expect(within(cards[0]).getByText('300.9조')).toBeInTheDocument();
    expect(within(cards[0]).getByText('2025년')).toBeInTheDocument();
    expect(within(cards[2]).getByText('미제공')).toBeInTheDocument();
    expect(within(cards[3]).getByText('125,000')).toBeInTheDocument();
    expect(within(cards[4]).getByText('1.2억')).toBeInTheDocument();
    expect(within(cards[5]).getByText('8.6')).toBeInTheDocument();
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

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('GrowthTrendCard', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('draws bars with rates, breaks at a missing year and switches metric without refetching', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        success: true,
        data: {
          range: { from: 2021, to: 2025 },
          series: [
            {
              key: 'revenue',
              points: [
                { year: 2021, value: 279_600_000_000_000, changeRate: null },
                { year: 2022, value: 302_200_000_000_000, changeRate: 8.1 },
                { year: 2024, value: 295_800_000_000_000, changeRate: null },
                { year: 2025, value: 300_900_000_000_000, changeRate: 1.7 },
              ],
            },
            {
              key: 'employee_count',
              points: [{ year: 2025, value: 125_000, changeRate: 2.5 }],
            },
          ],
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<GrowthTrendCard corpCode="00126380" />);

    const chart = await screen.findByRole('img', { name: /매출액 2021~2025년 변화 그래프/ });
    expect(within(chart).getAllByTestId('bar')).toHaveLength(4);
    expect(within(chart).getAllByTestId('rate-point')).toHaveLength(2);
    expect(within(chart).getByText('미제공')).toBeInTheDocument();
    expect(within(chart).getByText('+8.1%')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: '직원 수' }));
    expect(screen.getByRole('heading', { name: '직원 수 추이' })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('explains when the selected metric has no series', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json({ success: true, data: { range: { from: 2021, to: 2025 }, series: [] } }),
      ),
    );
    render(<GrowthTrendCard corpCode="A" />);
    expect(await screen.findByText('매출액 추이 데이터가 없습니다')).toBeInTheDocument();
  });
});
