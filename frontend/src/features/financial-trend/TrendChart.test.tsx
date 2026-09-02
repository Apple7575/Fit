import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TrendChart } from './TrendChart';
import type { TrendSeries } from './types';

const series: TrendSeries = {
  key: 'revenue',
  points: [
    { year: 2021, value: 279_604_800_000_000, changeRate: null },
    { year: 2022, value: 302_231_400_000_000, changeRate: 8.1 },
    { year: 2023, value: null, changeRate: null },
    { year: 2024, value: 300_870_903_000_000, changeRate: null },
    { year: 2025, value: 310_000_000_000_000, changeRate: 3.0 },
  ],
};

describe('TrendChart', () => {
  it('lists the year-over-year rate per year and leaves unknown years blank', () => {
    render(<TrendChart series={series} />);

    const strip = screen.getByTestId('change-rate-strip');
    const cells = within(strip).getAllByRole('listitem');
    expect(cells).toHaveLength(5);
    expect(cells[1]).toHaveTextContent('+8.1%');
    expect(cells[4]).toHaveTextContent('+3.0%');
    expect(cells[0]).not.toHaveTextContent('%');
    expect(cells[2]).not.toHaveTextContent('%');
  });

  it('adds the year-over-year rate to the tooltip when known', () => {
    render(<TrendChart series={series} />);

    fireEvent.focus(screen.getByRole('button', { name: '2022년 302조 2,314억 원' }));
    expect(screen.getByRole('tooltip')).toHaveTextContent('전년 대비 +8.1%');

    fireEvent.focus(screen.getByRole('button', { name: '2024년 300조 8,709억 원' }));
    expect(screen.getByRole('tooltip')).not.toHaveTextContent('전년 대비');
  });

  it('labels the x axis with every year from 2021 to 2025 in order', () => {
    render(<TrendChart series={series} />);

    const xAxis = screen.getByTestId('x-axis');
    expect(within(xAxis).getAllByText(/^\d{4}$/).map((n) => n.textContent)).toEqual([
      '2021',
      '2022',
      '2023',
      '2024',
      '2025',
    ]);
  });

  it('names the y axis with the metric and the currency unit', () => {
    render(<TrendChart series={series} />);

    expect(screen.getByTestId('y-axis-label')).toHaveTextContent('매출액 (원)');
  });

  it('renders a marker for every year that has a value and none for a missing year', () => {
    render(<TrendChart series={series} />);

    const markers = screen.getAllByRole('button', { name: /^\d{4}년/ });
    expect(markers.map((m) => m.getAttribute('aria-label'))).toEqual([
      '2021년 279조 6,048억 원',
      '2022년 302조 2,314억 원',
      '2024년 300조 8,709억 원',
      '2025년 310조 원',
    ]);
  });

  it('shows the year and value in a tooltip when a marker is hovered or focused', () => {
    render(<TrendChart series={series} />);

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.focus(screen.getByRole('button', { name: '2024년 300조 8,709억 원' }));

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('2024년');
    expect(tooltip).toHaveTextContent('300조 8,709억 원');
  });

  it('snaps the crosshair to the nearest year on pointer move', () => {
    render(<TrendChart series={series} />);
    const svg = screen.getByTestId('trend-svg');

    // jsdom 은 레이아웃이 없으므로 getBoundingClientRect 를 고정한다.
    svg.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 640, height: 280 }) as DOMRect;

    fireEvent.pointerMove(svg, { clientX: 630, clientY: 100 });

    expect(screen.getByRole('tooltip')).toHaveTextContent('2025년');
  });

  it('explains a missing year instead of showing 0', () => {
    render(<TrendChart series={series} />);
    const svg = screen.getByTestId('trend-svg');
    svg.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 640, height: 280 }) as DOMRect;

    fireEvent.pointerMove(svg, { clientX: 320, clientY: 100 });

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('2023년');
    expect(tooltip).toHaveTextContent('미제공');
    expect(tooltip).not.toHaveTextContent(/\b0\s*원/);
  });

  it('scales to its container instead of a fixed pixel width', () => {
    render(<TrendChart series={series} />);
    const svg = screen.getByTestId('trend-svg');

    expect(svg).toHaveAttribute('viewBox');
    expect(svg).not.toHaveAttribute('width');
    expect(svg).toHaveClass('w-full');
  });

  it('offers the same numbers as a table for screen readers', () => {
    render(<TrendChart series={series} />);

    const table = screen.getByRole('table', { name: '매출액 연도별 값' });
    expect(within(table).getAllByRole('row')).toHaveLength(6); // header + 5
    // 2023 은 값·증감률 모두 미제공
    expect(within(table).getAllByText('미제공').length).toBeGreaterThanOrEqual(2);
  });
});
