import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KeyMetricsSection } from './KeyMetricsSection';
import type { KeyMetric } from './types';

const metrics: KeyMetric[] = [
  { key: 'revenue', value: 300_870_903_000_000 },
  { key: 'operatingProfit', value: 6_566_976_000_000 },
  { key: 'netIncome', value: 15_487_100_000_000 },
  { key: 'totalAssets', value: 455_905_980_000_000 },
  { key: 'totalLiabilities', value: 92_228_115_000_000 },
  { key: 'totalEquity', value: null },
];

describe('KeyMetricsSection', () => {
  it('renders six cards whose labels match their values', () => {
    render(<KeyMetricsSection metrics={metrics} year={2025} />);

    const cards = screen.getAllByRole('article');
    expect(cards).toHaveLength(6);

    const revenue = screen.getByRole('article', { name: '매출액' });
    expect(within(revenue).getByText('300조 8,709억')).toBeInTheDocument();

    const liabilities = screen.getByRole('article', { name: '부채총계' });
    expect(within(liabilities).getByText('92조 2,281억')).toBeInTheDocument();
  });

  it('shows the base year and the currency unit', () => {
    render(<KeyMetricsSection metrics={metrics} year={2025} />);

    expect(
      screen.getByRole('heading', { name: '2025년 핵심지표' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('원')).toHaveLength(5);
  });

  it('marks a missing value as 미제공 instead of 0', () => {
    render(<KeyMetricsSection metrics={metrics} year={2025} />);

    const equity = screen.getByRole('article', { name: '자본총계' });
    expect(within(equity).getByText('미제공')).toBeInTheDocument();
    expect(within(equity).queryByText('0')).not.toBeInTheDocument();
  });

  it('keeps the six cards in a fixed order even if the input order differs', () => {
    render(
      <KeyMetricsSection metrics={[...metrics].reverse()} year={2025} />,
    );

    const labels = screen
      .getAllByRole('article')
      .map((card) => card.getAttribute('aria-label'));
    expect(labels).toEqual([
      '매출액',
      '영업이익',
      '당기순이익',
      '자산총계',
      '부채총계',
      '자본총계',
    ]);
  });
});
