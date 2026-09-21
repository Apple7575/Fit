import { fireEvent, render, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HomePage } from './HomePage';

const renderHome = () => {
  const router = createMemoryRouter(
    [
      { path: '/', element: <HomePage /> },
      { path: '/companies', element: <h1>기업 분석 화면</h1> },
      { path: '/companies/:corpCode/overview', element: <h1>상세 화면</h1> },
    ],
    { initialEntries: ['/'] },
  );

  render(<RouterProvider router={router} />);

  return router;
};

describe('HomePage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('검색창 대신 세 기능으로 가는 입구를 보여준다', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(
      screen.getByRole('heading', { level: 1, name: /기업의 눈으로 보는 나의 Fit/ }),
    ).toBeInTheDocument();
    // 기업 검색은 '기업 분석' 화면이 맡는다
    expect(screen.queryByLabelText('기업명')).not.toBeInTheDocument();

    const entries = screen.getByRole('list', { name: '바로 가기' });
    expect(within(entries).getByRole('link', { name: /기업 분석/ })).toHaveAttribute('href', '/companies');
    expect(within(entries).getByRole('link', { name: /자소서 검토/ })).toHaveAttribute(
      'href',
      '/cover-letters/new',
    );
    expect(within(entries).getByRole('link', { name: /모의 면접/ })).toHaveAttribute('href', '/interviews');
  });

  it('네 장을 순서대로 쌓고 섹션 점을 보여준다', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    expect(screen.getByRole('heading', { name: /코치 다섯이 붙습니다/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /묻고, 들어줍니다/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /궁금한 회사부터 시작해 보세요/ })).toBeInTheDocument();

    const dots = screen.getByRole('navigation', { name: '섹션 이동' });
    expect(within(dots).getAllByRole('button')).toHaveLength(4);

    const cta = screen.getByRole('list', { name: '분석 가능한 기업' });
    expect(within(cta).getByRole('link', { name: 'NAVER' })).toHaveAttribute(
      'href',
      '/companies/00266961/overview',
    );
  });

  it('첫 장은 영상 위에서 시작한다', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    /*
     * 세 기능 화면이 모두 영상 한 장으로 시작하는데 랜딩만 흰 종이였다. 처음 만나는 화면이
     * 가장 약하면 순서가 거꾸로다. 기업 목록은 기업 분석 첫 화면이 이미 보여주므로 여기서는
     * 뺐다 — 랜딩은 이 서비스가 무엇인지만 말한다.
     */
    const hero = document.getElementById('hero');
    expect(hero?.querySelector('video')).toHaveAttribute('src', '/landing/turn.mp4');
    expect(screen.queryByRole('list', { name: '바로 볼 수 있는 기업' })).not.toBeInTheDocument();
  });

  it('검토 방 대본은 사용자 질문부터 보여준다', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    // jsdom 에는 IntersectionObserver 가 없어 "화면 안"으로 간주되고, 첫 줄(사용자 질문)이 바로 보인다
    expect(screen.getByText(/삼성전자 DS 부문 지원동기 문항/)).toBeInTheDocument();
  });

  it('"지금 시작하기"는 기업 분석 화면으로 보낸다', () => {
    vi.stubGlobal('fetch', vi.fn());
    const router = renderHome();

    fireEvent.click(screen.getByRole('button', { name: '지금 시작하기' }));

    expect(router.state.location.pathname).toBe('/companies');
  });
});
