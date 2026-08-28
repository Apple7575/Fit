import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KeyMetricsGrid } from './KeyMetricsGrid';
import type { KeyMetric } from '../../types/metrics';

const metrics: KeyMetric[] = [
  { key: 'revenue', value: 300_870_903_000_000 },
  { key: 'operating_profit', value: 6_566_976_000_000 },
  { key: 'employee_count', value: 124_804 },
  { key: 'avg_salary', value: 130_000_000 },
  { key: 'avg_tenure', value: 12.4 },
  { key: 'rd_ratio', value: null },
];

describe('KeyMetricsGrid', () => {
  it('renders six cards whose labels match their values', () => {
    render(<KeyMetricsGrid metrics={metrics} />);

    expect(screen.getAllByRole('article')).toHaveLength(6);

    const revenue = screen.getByRole('article', { name: '매출액' });
    expect(within(revenue).getByText('300조 8,709억')).toBeInTheDocument();

    const employees = screen.getByRole('article', { name: '직원 수' });
    expect(within(employees).getByText('124,804')).toBeInTheDocument();
  });

  it('shows the unit that matches each metric', () => {
    render(<KeyMetricsGrid metrics={metrics} />);

    const unitOf = (name: string) =>
      within(screen.getByRole('article', { name })).getByText(/^(원|명|년|%)$/)
        .textContent;

    expect(unitOf('매출액')).toBe('원');
    expect(unitOf('직원 수')).toBe('명');
    expect(unitOf('1인 평균 급여')).toBe('원');
    expect(unitOf('평균 근속')).toBe('년');
  });

  it('marks a missing value as 미제공 instead of 0', () => {
    render(<KeyMetricsGrid metrics={metrics} />);

    const ratio = screen.getByRole('article', { name: 'R&D / 매출' });
    expect(within(ratio).getByText('미제공')).toBeInTheDocument();
    expect(within(ratio).queryByText('0')).not.toBeInTheDocument();
  });

  it('keeps the six cards in a fixed order even if the input order differs', () => {
    render(<KeyMetricsGrid metrics={[...metrics].reverse()} />);

    const labels = screen
      .getAllByRole('article')
      .map((card) => card.getAttribute('aria-label'));
    expect(labels).toEqual([
      '매출액',
      '영업이익',
      '직원 수',
      '1인 평균 급여',
      '평균 근속',
      'R&D / 매출',
    ]);
  });
});
