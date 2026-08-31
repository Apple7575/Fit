import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createAppRouter } from './router';

const renderRoute = (path: string) => {
  render(<RouterProvider router={createAppRouter([path])} />);
};

describe('application routes', () => {
  beforeEach(() => {
    // 상세 페이지의 데이터 섹션들이 네트워크를 타지 않도록 URL 별 응답을 돌려준다
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const ok = (data: unknown, status = 200) =>
          Promise.resolve(
            new Response(JSON.stringify({ success: status === 200, data }), {
              status,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        if (url.includes('/timeseries')) {
          return ok({ series: [] });
        }
        if (url.includes('/metrics')) {
          return ok({ metrics: [] });
        }
        if (url.includes('/industry-comparison')) {
          return ok({ year: 2025, industry: null, metrics: [], companies: [] });
        }
        // 기업 기본정보: 아는 기업이면 이름을, 모르면 404 를 돌려준다
        if (url.includes('/companies/00126380')) {
          return ok({
            corpCode: '00126380',
            corpName: '삼성전자',
            stockCode: '005930',
            industryCode: '26',
            industryName: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
            market: 'KOSPI',
            ceo: null,
            establishedDate: null,
          });
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              success: false,
              error: { code: 'COMPANY_NOT_FOUND', message: '해당 기업을 찾을 수 없습니다.' },
            }),
            { status: 404, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }),
    );
  });

  it('renders the company search home at the root path', () => {
    renderRoute('/');

    expect(
      screen.getByRole('heading', { level: 1, name: '기업 변화 분석' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('searchbox', { name: '기업명' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
  });

  it('renders the company analysis layout on the detail route', async () => {
    renderRoute('/companies/00126380');

    expect(
      await screen.findByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: '2025년 핵심지표' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: '최근 5개년 변화' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: '같은 산업 비교' }),
    ).toBeInTheDocument();
  });

  it('keeps unknown company metadata route-neutral', async () => {
    renderRoute('/companies/000000');

    expect(
      screen.getByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText('산업 정보 없음 · 기업코드 000000'),
    ).toBeInTheDocument();
  });

  it('renders a not-found page for unknown paths', () => {
    renderRoute('/unknown');

    expect(
      screen.getByRole('heading', { name: '페이지를 찾을 수 없습니다' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '홈으로 돌아가기' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});
