import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api/client';
import type { CompanyDetail } from '../company-detail/api';
import { CompanyBasicInfoCard } from './CompanyBasicInfoCard';

const fullDetail: CompanyDetail = {
  corpCode: '00126380',
  corpName: '삼성전자',
  industryCode: '26',
  industryName: '전기·전자제품 제조업',
  ceo: '한종희, 경계현',
  establishedDate: '1969-01-13',
  address: '경기도 수원시 영통구 삼성로 129',
  homepageUrl: 'https://www.samsung.com',
  dataYear: 2025,
};

describe('CompanyBasicInfoCard', () => {
  it('성공 시 기본정보 필드를 모두 보여준다', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{ status: 'success', data: fullDetail }}
      />,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(screen.getByText('전기·전자제품 제조업')).toBeInTheDocument();
    expect(screen.getByText('한종희, 경계현')).toBeInTheDocument();
    expect(screen.getByText('1969년 1월 13일')).toBeInTheDocument();
    expect(
      screen.getByText('경기도 수원시 영통구 삼성로 129'),
    ).toBeInTheDocument();

    const homepage = screen.getByRole('link', { name: /samsung\.com/ });
    expect(homepage).toHaveAttribute('href', 'https://www.samsung.com');
    expect(homepage).toHaveAttribute('target', '_blank');
  });

  it('null 필드는 "정보 없음" 으로 표시하고 홈페이지 링크는 만들지 않는다', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{
          status: 'success',
          data: {
            ...fullDetail,
            ceo: null,
            establishedDate: null,
            address: null,
            homepageUrl: null,
          },
        }}
      />,
    );

    expect(screen.getAllByText('정보 없음')).toHaveLength(4);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('오류여도 카드는 유지된다 (F-31)', () => {
    render(
      <CompanyBasicInfoCard
        corpCode="00126380"
        state={{
          status: 'error',
          error: new ApiError(500, 'INTERNAL_ERROR', '서버 오류'),
        }}
      />,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('정보 없음').length).toBeGreaterThan(0);
  });
});
