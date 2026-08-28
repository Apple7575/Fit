import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IndustryComparisonSection } from './IndustryComparisonSection';
import type { IndustryComparison } from './types';

const comparisons: IndustryComparison[] = [
  {
    metricKey: 'revenue',
    year: 2025,
    industryName: '반도체 제조업',
    peers: [
      { corpCode: '00126380', corpName: '삼성전자', value: 300_870_903_000_000 },
      { corpCode: '00164779', corpName: 'SK하이닉스', value: 66_193_000_000_000 },
      { corpCode: '00113058', corpName: 'DB하이텍', value: null },
    ],
  },
  {
    metricKey: 'operating_profit',
    year: 2025,
    industryName: '반도체 제조업',
    peers: [
      { corpCode: '00126380', corpName: '삼성전자', value: 6_566_976_000_000 },
      { corpCode: '00113058', corpName: 'DB하이텍', value: -97_000_000_000 },
    ],
  },
];

const renderSection = () =>
  render(
    <IndustryComparisonSection
      comparisons={comparisons}
      corpCode="00126380"
    />,
  );

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
  it('describes which industry, metric and year are compared', () => {
    renderSection();

    expect(
      screen.getByRole('heading', { level: 2, name: '같은 산업 비교' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/반도체 제조업/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액/)).toBeInTheDocument();
  });

  it('lists peers of the default metric with formatted values', () => {
    renderSection();

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(peerRow('삼성전자').getByText('300조 8,709억')).toBeInTheDocument();
  });

  it('marks the company being viewed', () => {
    renderSection();

    expect(peerRow('삼성전자').getByText('조회 기업')).toBeInTheDocument();
    expect(peerRow('SK하이닉스').queryByText('조회 기업')).not.toBeInTheDocument();
  });

  it('shows 미제공 instead of 0 when a value is missing', () => {
    renderSection();

    expect(peerRow('DB하이텍').getByText('미제공')).toBeInTheDocument();
  });

  it('switches the compared metric', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '영업이익' }));

    expect(screen.getByText(/2025년 영업이익/)).toBeInTheDocument();
    expect(peerRow('삼성전자').getByText('6조 5,670억')).toBeInTheDocument();
    expect(screen.queryByText('SK하이닉스')).not.toBeInTheDocument();
  });

  it('explains when the chosen metric has no comparison data', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '평균 근속' }));

    expect(screen.getByText(/평균 근속 비교 정보가 없습니다/)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('keeps showing the industry and year when the metric has no data', () => {
    renderSection();

    fireEvent.click(screen.getByRole('radio', { name: '평균 근속' }));

    // 산업·연도는 지표와 무관한 값이라 사라지면 안 된다.
    expect(screen.getByText(/반도체 제조업/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 평균 근속/)).toBeInTheDocument();
  });

  it('reverses the order when a different sort is chosen', () => {
    renderSection();

    expect(peerNames()).toEqual(['삼성전자', 'SK하이닉스', 'DB하이텍']);

    fireEvent.click(screen.getByRole('radio', { name: '값이 작은 순' }));

    // 값이 없는 DB하이텍은 방향과 무관하게 항상 마지막이다.
    expect(peerNames()).toEqual(['SK하이닉스', '삼성전자', 'DB하이텍']);
  });

  it('starts sorted from the largest value', () => {
    renderSection();

    expect(screen.getByRole('radio', { name: '값이 큰 순' })).toBeChecked();
  });
});
