import { render, screen } from '@testing-library/react';
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

  it('switches the chart to the requested metric', () => {
    render(<FinancialTrendSection metricKey="totalEquity" series={series} />);

    expect(
      screen.getByRole('img', { name: '자본총계 2021~2025년 변화 그래프' }),
    ).toBeInTheDocument();
  });

  it('shows an empty message when the metric has no series', () => {
    render(<FinancialTrendSection series={[]} />);

    expect(screen.getByText('매출액 추이 데이터가 없습니다')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
