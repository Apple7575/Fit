import { fireEvent, render, screen, within } from '@testing-library/react';
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
    vi.useRealTimers();
  });

  it('shows no result panel before searching', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByText(/검색 결과/)).not.toBeInTheDocument();
  });

  it('opens with the video hero and stacks the four snap sections', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(
      screen.getByRole('heading', { level: 1, name: /기업의 눈으로 보는 나의 Fit/ }),
    ).toBeInTheDocument();

    // 배경 영상은 자동재생·반복·무음
    const video = screen.getByLabelText('Fit 서비스 소개 영상') as HTMLVideoElement;
    expect(video).toHaveAttribute('autoplay');
    expect(video).toHaveAttribute('loop');
    expect(video.muted).toBe(true);

    // 섹션 순서: 히어로 → 코치(검토 방) → AI 면접 → 시작하기
    expect(screen.getByRole('heading', { name: /코치 다섯이 붙습니다/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /묻고, 들어줍니다/ })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /궁금한 회사부터 시작해 보세요/ }),
    ).toBeInTheDocument();

    // 섹션 점 내비
    const dots = screen.getByRole('navigation', { name: '섹션 이동' });
    expect(within(dots).getAllByRole('button')).toHaveLength(4);

    expect(screen.getByRole('link', { name: '자소서 써 보기' })).toHaveAttribute(
      'href',
      '/cover-letters/new',
    );
    expect(screen.getByRole('link', { name: '모의 면접 시작' })).toHaveAttribute(
      'href',
      '/interviews',
    );
    const cta = screen.getByRole('list', { name: '분석 가능한 기업' });
    expect(within(cta).getByRole('link', { name: 'NAVER' })).toHaveAttribute(
      'href',
      '/companies/00266961/overview',
    );
  });

  it('shows the review-room script with the user question first', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    // jsdom 에는 IntersectionObserver 가 없어 "화면 안"으로 간주되고, 첫 줄(사용자 질문)이 바로 보인다
    expect(screen.getByText(/삼성전자 DS 부문 지원동기 문항/)).toBeInTheDocument();
  });

  it('sends "지금 시작하기" back to the hero search box', () => {
    vi.stubGlobal('fetch', vi.fn());
    vi.useFakeTimers();
    renderHome();

    fireEvent.click(screen.getByRole('button', { name: '지금 시작하기' }));
    // 히어로 회사명 회전 interval 이 계속 돌기 때문에 runAllTimers 대신 시간을 정해 진행한다
    vi.advanceTimersByTime(500);

    expect(screen.getByLabelText('기업명')).toHaveFocus();
  });

  it('shows a loading state and then the companies returned by the API', async () => {
    const fetchMock = vi.fn().mockResolvedValue(searchResponse([samsung]));
    vi.stubGlobal('fetch', fetchMock);
    renderHome();

    search('삼성');

    expect(screen.getByRole('status')).toHaveTextContent('검색 중입니다');
    expect(await screen.findByRole('button', { name: /삼성전자/ })).toBeInTheDocument();

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/companies?');
    expect(url).toContain(`keyword=${encodeURIComponent('삼성')}`);
  });

  it('moves to the detail route using the corp code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(searchResponse([samsung])));
    const router = renderHome();

    search('삼성');
    fireEvent.click(await screen.findByRole('button', { name: /삼성전자/ }));

    expect(await screen.findByRole('heading', { name: '상세 화면' })).toBeInTheDocument();
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

    expect(await screen.findByRole('alert')).toHaveTextContent('검색 중 문제가 발생했습니다');

    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));

    expect(await screen.findByRole('button', { name: /삼성전자/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
