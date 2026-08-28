import { render, screen } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createAppRouter } from './router';

const renderRoute = (path: string) => {
  render(<RouterProvider router={createAppRouter([path])} />);
};

describe('application routes', () => {
  beforeEach(() => {
    // 상세 페이지의 데이터 섹션들이 네트워크를 타지 않도록 URL 별 빈 응답을 돌려준다
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const data = url.includes('/timeseries')
          ? { series: [] }
          : { metrics: [] };
        return Promise.resolve(
          new Response(JSON.stringify({ success: true, data }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
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

  it('renders the company analysis layout on the detail route', () => {
    renderRoute('/companies/005930');

    expect(
      screen.getByRole('heading', { level: 1, name: '삼성전자' }),
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

  it('keeps unknown company metadata route-neutral', () => {
    renderRoute('/companies/000000');

    expect(
      screen.getByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('기업 정보 준비 중 · 기업코드 000000'),
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
