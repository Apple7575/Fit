import { fireEvent, render, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Company } from '../../types/company';
import { CompanySearchPage } from './CompanySearchPage';

const samsung: Company = {
  corpCode: '00126380',
  corpName: '삼성전자',
  stockCode: '005930',
  industryCode: '264',
  industryName: '반도체 제조업',
};

const searchResponse = (items: Company[]) =>
  new Response(JSON.stringify({ success: true, data: { items, total: items.length } }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

const renderPage = () => {
  const router = createMemoryRouter(
    [
      { path: '/companies', element: <CompanySearchPage /> },
      { path: '/companies/:corpCode/overview', element: <h1>상세 화면</h1> },
    ],
    { initialEntries: ['/companies'] },
  );
  render(<RouterProvider router={router} />);
  return router;
};

describe('CompanySearchPage', () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it('starts with the search box, an empty recent list and the featured companies', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderPage();

    expect(
      screen.getByRole('heading', { level: 1, name: /어느 회사를 볼까요/ }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('기업명')).toBeInTheDocument();
    // 본 기업이 없으면 최근 목록 자체를 띄우지 않는다 (첫 화면은 검색만 남긴다)
    expect(screen.queryByRole('region', { name: '최근 본 기업' })).not.toBeInTheDocument();

    const featured = screen.getByRole('region', { name: '바로 볼 수 있는 기업' });
    expect(within(featured).getByRole('link', { name: 'NAVER' })).toHaveAttribute(
      'href',
      '/companies/00266961/overview',
    );
  });

  it('opens the overview of a searched company and remembers it as recently viewed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(searchResponse([samsung])));
    const router = renderPage();

    fireEvent.change(screen.getByLabelText('기업명'), { target: { value: '삼성' } });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));
    fireEvent.click(await screen.findByRole('button', { name: /삼성전자/ }));

    expect(await screen.findByRole('heading', { name: '상세 화면' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/companies/00126380/overview');
    expect(JSON.parse(window.localStorage.getItem('recent-companies') ?? '[]')).toEqual([
      { corpCode: '00126380', corpName: '삼성전자' },
    ]);
  });

  it('lists recently viewed companies and can clear them', () => {
    vi.stubGlobal('fetch', vi.fn());
    window.localStorage.setItem(
      'recent-companies',
      JSON.stringify([{ corpCode: '00126380', corpName: '삼성전자' }]),
    );
    renderPage();

    const recent = screen.getByRole('region', { name: '최근 본 기업' });
    expect(within(recent).getByRole('button', { name: '삼성전자' })).toBeInTheDocument();

    fireEvent.click(within(recent).getByRole('button', { name: '지우기' }));

    expect(screen.queryByRole('region', { name: '최근 본 기업' })).not.toBeInTheDocument();
    expect(window.localStorage.getItem('recent-companies')).toBeNull();
  });
});
