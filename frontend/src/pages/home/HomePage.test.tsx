import { fireEvent, render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Company } from '../../types/company';
import { HomePage } from './HomePage';

const samsung: Company = {
  corpCode: '00126380',
  corpName: '삼성전자',
  stockCode: '005930',
  industryCode: '264',
  industryName: '반도체 제조업',
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const searchResponse = (items: Company[], total = items.length) =>
  json({ success: true, data: { items, total } });

const renderHome = () => {
  const router = createMemoryRouter(
    [
      { path: '/', element: <HomePage /> },
      {
        path: '/companies/:corpCode',
        element: <h1>상세 화면</h1>,
      },
    ],
    { initialEntries: ['/'] },
  );

  render(<RouterProvider router={router} />);

  return router;
};

const search = (keyword: string) => {
  fireEvent.change(screen.getByLabelText('기업명'), {
    target: { value: keyword },
  });
  fireEvent.click(screen.getByRole('button', { name: '검색' }));
};

describe('HomePage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows no result panel before searching', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('shows a loading state and then the companies returned by the API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(searchResponse([samsung]));
    vi.stubGlobal('fetch', fetchMock);
    renderHome();

    search('삼성');

    expect(screen.getByRole('status')).toHaveTextContent('검색 중입니다');
    expect(
      await screen.findByRole('button', { name: /삼성전자/ }),
    ).toBeInTheDocument();

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/companies?');
    expect(url).toContain(`keyword=${encodeURIComponent('삼성')}`);
  });

  it('moves to the detail route using the corp code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(searchResponse([samsung])));
    const router = renderHome();

    search('삼성');
    fireEvent.click(await screen.findByRole('button', { name: /삼성전자/ }));

    expect(
      await screen.findByRole('heading', { name: '상세 화면' }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/companies/00126380');
  });

  it('shows an empty message when the API returns no items', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(searchResponse([])));
    renderHome();

    search('없는기업');

    expect(await screen.findByText(/검색 결과가 없습니다/)).toBeInTheDocument();
  });

  it('shows an error state when the request fails, and retries', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(searchResponse([samsung]));
    vi.stubGlobal('fetch', fetchMock);
    renderHome();

    search('삼성');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '검색 중 문제가 발생했습니다',
    );

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));

    expect(
      await screen.findByRole('button', { name: /삼성전자/ }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
