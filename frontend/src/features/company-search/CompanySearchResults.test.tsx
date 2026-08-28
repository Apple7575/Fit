import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Company } from '../../types/company';
import { CompanySearchResults } from './CompanySearchResults';

const companies: Company[] = [
  {
    corpCode: '00126380',
    corpName: '삼성전자',
    stockCode: '005930',
    industryCode: '264',
    industryName: '반도체 제조업',
  },
  {
    corpCode: '00164779',
    corpName: 'SK하이닉스',
    stockCode: '000660',
    industryCode: '264',
    industryName: '반도체 제조업',
  },
];

describe('CompanySearchResults', () => {
  it('renders nothing before a search runs', () => {
    const { container } = render(
      <CompanySearchResults companies={[]} keyword="" status="idle" />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('announces that a search is running', () => {
    render(
      <CompanySearchResults companies={[]} keyword="삼성" status="loading" />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('검색 중입니다');
  });

  it('renders every matched company with its industry and stock code', () => {
    render(
      <CompanySearchResults
        companies={companies}
        keyword="반도체"
        status="success"
      />,
    );

    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByRole('button', { name: /삼성전자/ })).toBeInTheDocument();
    expect(screen.getByText('005930')).toBeInTheDocument();
    expect(screen.getAllByText('반도체 제조업')).toHaveLength(2);
  });

  it('falls back when industry and stock code are missing', () => {
    render(
      <CompanySearchResults
        companies={[
          {
            corpCode: '00999999',
            corpName: '비상장기업',
            stockCode: null,
            industryCode: null,
            industryName: null,
          },
        ]}
        keyword="비상장"
        status="success"
      />,
    );

    expect(screen.getByText('업종 정보 없음')).toBeInTheDocument();
    expect(screen.getByText('비상장')).toBeInTheDocument();
  });

  it('shows the total count reported by the server', () => {
    render(
      <CompanySearchResults
        companies={companies}
        keyword="삼성"
        status="success"
        total={2}
      />,
    );

    expect(screen.getByText(/검색 결과 2건/)).toBeInTheDocument();
    expect(screen.queryByText(/상위/)).not.toBeInTheDocument();
  });

  it('notes that only part of the results are shown', () => {
    render(
      <CompanySearchResults
        companies={companies}
        keyword="삼성"
        status="success"
        total={57}
      />,
    );

    expect(screen.getByText(/검색 결과 57건/)).toBeInTheDocument();
    expect(screen.getByText(/상위 2건 표시/)).toBeInTheDocument();
  });

  it('calls onSelect with the chosen company', () => {
    const onSelect = vi.fn();
    render(
      <CompanySearchResults
        companies={companies}
        keyword="삼성"
        onSelect={onSelect}
        status="success"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /삼성전자/ }));

    expect(onSelect).toHaveBeenCalledWith(companies[0]);
  });

  it('shows an empty message including the keyword', () => {
    render(
      <CompanySearchResults
        companies={[]}
        keyword="없는기업"
        status="success"
      />,
    );

    expect(screen.getByText(/없는기업/)).toBeInTheDocument();
    expect(screen.getByText(/검색 결과가 없습니다/)).toBeInTheDocument();
  });

  it('shows an error alert with a retry button', () => {
    const onRetry = vi.fn();
    render(
      <CompanySearchResults
        companies={[]}
        keyword="삼성"
        onRetry={onRetry}
        status="error"
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      '검색 중 문제가 발생했습니다',
    );

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
