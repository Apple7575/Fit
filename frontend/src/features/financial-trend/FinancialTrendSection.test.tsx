import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { mockFinancialTrendByCompany } from '../../mocks/financialTrend';
import { FinancialTrendSection } from './FinancialTrendSection';

const series = mockFinancialTrendByCompany['005930'];

describe('FinancialTrendSection', () => {
  it('renders the revenue chart by default with the 2021~2025 range in the subtitle', () => {
    render(<FinancialTrendSection series={series} />);

    expect(
      screen.getByRole('heading', { name: '최근 5개년 변화' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2021~2025년 매출액 변화/)).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: '매출액 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
  });

  it('offers all six metrics and marks revenue as the default selection', () => {
    render(<FinancialTrendSection series={series} />);

    const group = screen.getByRole('group', { name: '그래프 지표 선택' });
    const radios = screen.getAllByRole('radio');
    expect(group).toBeInTheDocument();
    expect(radios.map((r) => r.parentElement?.textContent)).toEqual([
      '매출액',
      '영업이익',
      '당기순이익',
      '자산총계',
      '부채총계',
      '자본총계',
    ]);
    expect(screen.getByRole('radio', { name: '매출액' })).toBeChecked();
    expect(screen.getByRole('radio', { name: '영업이익' })).not.toBeChecked();
  });

  it('updates the chart immediately when another metric is selected', async () => {
    const user = userEvent.setup();
    render(<FinancialTrendSection series={series} />);

    await user.click(screen.getByRole('radio', { name: '영업이익' }));

    expect(screen.getByRole('radio', { name: '영업이익' })).toBeChecked();
    expect(screen.getByRole('radio', { name: '매출액' })).not.toBeChecked();
    expect(
      screen.getByRole('img', { name: '영업이익 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2021~2025년 영업이익 변화/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '2021년 51조 6,339억 원' }),
    ).toBeInTheDocument();
  });

  it('honours an initial metric and still lets the user change it', async () => {
    const user = userEvent.setup();
    render(<FinancialTrendSection initialMetricKey="totalEquity" series={series} />);

    expect(screen.getByRole('radio', { name: '자본총계' })).toBeChecked();
    expect(
      screen.getByRole('img', { name: '자본총계 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: '자산총계' }));
    expect(
      screen.getByRole('img', { name: '자산총계 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
  });

  it('shows an empty message when the selected metric has no series', () => {
    render(<FinancialTrendSection series={[]} />);

    expect(screen.getByText('매출액 추이 데이터가 없습니다')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
