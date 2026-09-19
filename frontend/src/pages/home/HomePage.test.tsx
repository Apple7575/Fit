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

  it('바로 볼 수 있는 기업은 그 회사 요약으로 간다', () => {
    vi.stubGlobal('fetch', vi.fn());
    renderHome();

    const featured = screen.getByRole('list', { name: '바로 볼 수 있는 기업' });
    expect(within(featured).getByRole('link', { name: '삼성전자' })).toHaveAttribute(
      'href',
      '/companies/00126380/overview',
    );
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
