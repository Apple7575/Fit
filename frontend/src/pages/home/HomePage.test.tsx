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
    expect(screen.queryByText(/검색 결과/)).not.toBeInTheDocument();
  });

  it('tells the brand story and links every scene to the real analysis tab', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(
      screen.getByRole('heading', { level: 1, name: /기업은 숫자로 말합니다/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: '기분은 다섯 가지 질문만 남깁니다.' }),
    ).toBeInTheDocument();

    const sceneLinks = screen.getAllByRole('link', { name: /실제 화면에서 보기/ });
    expect(sceneLinks.map((a) => a.getAttribute('href'))).toEqual([
      '/companies/00126380/overview',
      '/companies/00126380/growth',
      '/companies/00126380/focus',
      '/companies/00126380/comparison',
      '/companies/00126380/issues',
    ]);
    expect(screen.getAllByRole('link', { name: /근거 보기/ })).toHaveLength(3);

    // 배경 영상은 자동재생하지 않고 스크롤에 따라 프레임을 넘긴다
    const video = screen.getByLabelText('기분 서비스 소개 영상') as HTMLVideoElement;
    expect(video.getAttribute('src')).toBe('/landing-scrub.mp4');
    expect(video).not.toHaveAttribute('autoplay');
    expect(video).not.toHaveAttribute('loop');
    expect(video).toHaveAttribute('playsinline');
    expect(video).toHaveAttribute('preload', 'auto');
    expect(video.muted).toBe(true);
    expect(screen.getByRole('link', { name: 'NAVER' })).toHaveAttribute(
      'href',
      '/companies/90000004/overview',
    );
  });

  it('sends the CTA buttons back to the hero search box', () => {
    vi.stubGlobal('fetch', vi.fn());
    vi.useFakeTimers();
    renderHome();

    fireEvent.click(screen.getByRole('button', { name: /기업명으로 검색하기/ }));
    vi.runAllTimers();

    expect(screen.getByLabelText('기업명')).toHaveFocus();
    vi.useRealTimers();
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
