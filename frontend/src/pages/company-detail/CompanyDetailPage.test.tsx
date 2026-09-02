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
      await screen.findByRole('heading', { name: /산업 비교/ }),
    ).toBeInTheDocument();
  });

  it('성장 분석 탭은 기준연도 핵심지표와 5년 추이를 보여준다', async () => {
    const fetchMock = stubFetchByUrl();
    vi.stubGlobal('fetch', fetchMock);

    renderAt('/companies/00126380/growth');

    expect(
      await screen.findByRole('heading', { name: '2025년 핵심지표' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '최근 5개년 변화' }),
    ).toBeInTheDocument();
    // 기준연도는 기본정보의 dataYear(2025) 를 그대로 넘기고, 연도 없는 선행 호출은 없다
    const metricsCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => /\/metrics(\?|$)/.test(url));
    expect(metricsCalls).toEqual([
      expect.stringContaining('year=2025'),
    ]);
  });

  it('미구현 탭은 비활성 버튼으로 표시된다', async () => {
    vi.stubGlobal('fetch', stubFetchByUrl());

    renderAt('/companies/00126380');
    await screen.findByRole('heading', { level: 1, name: '삼성전자' });

    for (const label of ['집중 분야', '최근 이슈']) {
      expect(screen.getByRole('button', { name: label })).toBeDisabled();
    }
    expect(screen.getByRole('link', { name: '성장 분석' })).toBeInTheDocument();
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
  });
});
