import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IndustryComparisonSection } from './IndustryComparisonSection';
import type { IndustryComparison } from './types';

const comparison: IndustryComparison = {
  metricKey: 'revenue',
  year: 2025,
  industryName: '반도체 제조업',
  peers: [
    { corpCode: '00126380', corpName: '삼성전자', value: 300_870_903_000_000 },
    { corpCode: '00164779', corpName: 'SK하이닉스', value: 66_193_000_000_000 },
    { corpCode: '00113058', corpName: 'DB하이텍', value: null },
  ],
};

const renderSection = (props?: Partial<IndustryComparison>) =>
  render(
    <IndustryComparisonSection
      comparison={{ ...comparison, ...props }}
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

describe('IndustryComparisonSection', () => {
  it('describes which industry, metric and year are compared', () => {
    renderSection();

    expect(
      screen.getByRole('heading', { level: 2, name: '같은 산업 비교' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/반도체 제조업/)).toBeInTheDocument();
    expect(screen.getByText(/2025년 매출액/)).toBeInTheDocument();
  });

  it('lists every peer with its formatted value', () => {
    renderSection();

    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(peerRow('삼성전자').getByText('300조 8,709억')).toBeInTheDocument();
    expect(peerRow('SK하이닉스').getByText('66조 1,930억')).toBeInTheDocument();
  });

  it('marks the company being viewed', () => {
    renderSection();

    expect(peerRow('삼성전자').getByText('조회 기업')).toBeInTheDocument();
    expect(peerRow('SK하이닉스').queryByText('조회 기업')).not.toBeInTheDocument();
  });

  it('shows 미제공 instead of 0 when a value is missing', () => {
    renderSection();

    expect(peerRow('DB하이텍').getByText('미제공')).toBeInTheDocument();
    expect(peerRow('DB하이텍').queryByText('0')).not.toBeInTheDocument();
  });

  it('explains when the industry has no comparable company', () => {
    renderSection({ peers: [] });

    expect(
      screen.getByText(/비교할 동종 기업 정보가 없습니다/),
    ).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('falls back when the industry is unknown', () => {
    renderSection({ industryName: null });

    expect(screen.getByText(/산업 정보 없음/)).toBeInTheDocument();
  });
});
