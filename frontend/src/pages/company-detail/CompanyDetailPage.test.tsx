import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAppRouter } from '../../app/router';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const detailBody = {
  success: true,
  data: {
    corpCode: '00126380',
    corpName: '삼성전자',
    stockCode: '005930',
    industryCode: '26',
    industryName: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
    market: 'KOSPI',
    ceo: '전영현',
    establishedDate: '1969-01-13',
    address: '경기도 수원시 영통구 삼성로 129',
    homepageUrl: 'https://www.samsung.com',
    dataYear: 2025,
  },
};

const profileBody = {
  success: true,
  data: {
    year: 2025,
    businesses: ['반도체'],
    segments: [{ code: 'DS', revenue: 1000, revenueShare: 100 }],
    totalRevenue: 1000,
    products: ['HBM'],
  },
};

const emptyComparison = {
  success: true,
  data: { year: 2025, industry: null, metrics: [], companies: [] },
};

/** 상세 레이아웃·탭이 부르는 API 를 URL 로 구분해 응답한다. */
const stubFetchByUrl = (
  detail: Response | (() => Response) = () => json(detailBody),
) =>
  vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/profile')) {
      return Promise.resolve(json(profileBody));
    }
    if (url.includes('/industry-comparison')) {
      return Promise.resolve(json(emptyComparison));
    }
    if (url.includes('/news/stats')) {
      return Promise.resolve(new Response('Not Found', { status: 404 }));
    }
    if (url.includes('/news/top')) {
      return Promise.resolve(json({ success: true, data: { items: [] } }));
    }
    if (url.includes('/news')) {
      return Promise.resolve(
        json({
          success: true,
          data: {
            items: [
              {
                id: 1,
                title: '테스트 뉴스',
                description: null,
                publishedAt: '2025-05-13',
                originalUrl: 'https://news.example.com/1',
              },
            ],
            total: 1,
          },
        }),
      );
    }
    if (url.includes('/api/industries/')) {
      return Promise.resolve(
        json({ success: true, data: { industry: null, companies: [] } }),
      );
    }
    if (url.includes('/metrics/timeseries')) {
      return Promise.resolve(
        json({
          success: true,
          data: { range: { from: 2021, to: 2025 }, series: [] },
        }),
      );
    }
    if (url.includes('/metrics')) {
      return Promise.resolve(
        json({
          success: true,
          data: {
            corpCode: '00126380',
            year: 2025,
            metrics: [
              { key: 'revenue', value: 1_0000_0000_0000, yoy: null },
            ],
            profitability: null,
          },
        }),
      );
    }
    if (url.includes('/activities')) {
      return Promise.resolve(
        json({
          success: true,
          data: {
            items: [
              { year: 2025, type: 'facility', field: '파운드리', purpose: '증설', amount: 1 },
            ],
          },
        }),
      );
    }
    if (url.includes('/segments')) {
      return Promise.resolve(
        json({ success: true, data: { year: 2025, employeeTotalChange: 10, segments: [] } }),
      );
    }
    if (url.includes('/focus')) {
      return Promise.resolve(new Response('Not Found', { status: 404 }));
    }
    return Promise.resolve(typeof detail === 'function' ? detail() : detail);
  });

const renderAt = (path: string) =>
  render(<RouterProvider router={createAppRouter([path])} />);

describe('CompanyDetailPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('/companies/:id 는 기업 개요 탭으로 리다이렉트한다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380');

    expect(
      await screen.findByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    // 데이터 기준 칩
    expect(screen.getByText('데이터 기준: 2025')).toBeInTheDocument();
  });

  it('탭 버튼으로 산업 비교 탭에 이동한다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());
    const user = userEvent.setup();

    renderAt('/companies/00126380');
    await screen.findByRole('heading', { level: 1, name: '삼성전자' });

    await user.click(screen.getByRole('link', { name: '산업 비교' }));

    expect(
      await screen.findByRole('heading', { name: '동일 산업 기업 비교' }),
    ).toBeInTheDocument();
  });

  it('성장 분석 탭은 기준연도 핵심지표와 5년 추이를 보여준다', async () => {
    const fetchMock = stubFetchByUrl();
    vi.stubGlobal('fetch', fetchMock);

    renderAt('/companies/00126380/growth');

    expect(
      await screen.findByRole('list', { name: '기준연도 핵심지표' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '매출액 추이' }),
    ).toBeInTheDocument();
    expect(screen.getByText('최근 5년 성장 분석 (2021–2025)')).toBeInTheDocument();
    // 기준연도는 기본정보의 dataYear(2025) 를 그대로 넘기고, 연도 없는 선행 호출은 없다
    const metricsCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => /\/metrics(\?|$)/.test(url));
    expect(metricsCalls).toEqual([
      expect.stringContaining('year=2025'),
    ]);
  });

  it('집중 분야 탭은 확정 영역을 보여주고 조건부 영역은 404 면 숨긴다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380/focus');

    expect(
      await screen.findByRole('heading', { name: '기업 집중 분야 분석' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '투자' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '인력 변화' }),
    ).toBeInTheDocument();
    expect((await screen.findAllByText('증설')).length).toBeGreaterThan(0);
    expect(
      screen.queryByRole('heading', { name: '사업 방향' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: '집중 분야 요약' }),
    ).not.toBeInTheDocument();
  });

  it('최근 이슈 탭은 통계·TOP 이 없어도 기본 뉴스 목록을 보여준다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380/issues');

    expect(
      await screen.findByRole('heading', { name: '최근 기업 이슈' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '최신 뉴스' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('link', { name: /테스트 뉴스/ }),
    ).toHaveAttribute('href', 'https://news.example.com/1');
    expect(screen.queryByRole('heading', { name: /중요 뉴스 TOP/ })).not.toBeInTheDocument();
    expect(screen.queryByText('최근 뉴스 수')).not.toBeInTheDocument();
    expect(await screen.findByText('데이터 기준: 2025.05.13')).toBeInTheDocument();
  });

  it('상세 탭 다섯 개가 모두 링크로 표시된다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380');
    await screen.findByRole('heading', { level: 1, name: '삼성전자' });

    for (const label of ['기업 개요', '성장 분석', '집중 분야', '산업 비교', '최근 이슈']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('기본정보 API 가 실패해도 페이지는 유지된다 (F-31)', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchByUrl(() =>
        json(
          { success: false, error: { code: 'INTERNAL_ERROR', message: 'x' } },
          500,
        ),
      ),
    );

    renderAt('/companies/00126380');

    expect(
      await screen.findByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    // 조건부 섹션은 별개 요청이라 정상 표시된다
    expect(
      await screen.findByRole('heading', { name: '주요 사업' }),
    ).toBeInTheDocument();
    // 실패를 "정보 없음"으로 위장하지 않고 안내 + 다시 시도를 보여준다
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /기업 기본정보를 불러오지 못했습니다/,
    );
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument();
  });

  it('기본정보가 404 면 기업 없음 안내만 보이고 개요 섹션은 내리지 않는다', async () => {
    // 개요 섹션은 기본정보와 나란히 요청되지만, 기업이 없다고 확인되면 응답과 무관하게 내리지 않는다
    vi.stubGlobal(
      'fetch',
      stubFetchByUrl(() =>
        json(
          { success: false, error: { code: 'COMPANY_NOT_FOUND', message: '없음' } },
          404,
        ),
      ),
    );

    renderAt('/companies/99999999');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '기업 정보를 찾을 수 없습니다. 기업코드(99999999)를 확인해 주세요.',
    );
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '주요 사업' })).not.toBeInTheDocument();
  });
});
