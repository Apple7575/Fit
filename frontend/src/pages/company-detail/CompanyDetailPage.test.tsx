import { render, screen } from '@testing-library/react';
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
  },
};

const emptyMetrics = {
  success: true,
  data: { corpCode: '00126380', year: 2025, metrics: [] },
};

const emptyTimeseries = {
  success: true,
  data: { range: { from: 2021, to: 2025 }, series: [] },
};

const emptyComparison = {
  success: true,
  data: { year: 2025, industry: null, metrics: [], companies: [] },
};

/** 상세 페이지가 부르는 4개 API 를 URL 로 구분해 응답한다. */
const stubFetchByUrl = (
  detail: Response | (() => Response) = () => json(detailBody),
) =>
  vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/metrics/timeseries')) {
      return Promise.resolve(json(emptyTimeseries));
    }
    if (url.includes('/metrics')) {
      return Promise.resolve(json(emptyMetrics));
    }
    if (url.includes('/industry-comparison')) {
      return Promise.resolve(json(emptyComparison));
    }
    return Promise.resolve(typeof detail === 'function' ? detail() : detail);
  });

const renderPage = () =>
  render(
    <RouterProvider router={createAppRouter(['/companies/00126380'])} />,
  );

describe('CompanyDetailPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows the company name and industry from the detail API', async () => {
    const fetchMock = stubFetchByUrl();
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    expect(
      await screen.findByRole('heading', { level: 1, name: '삼성전자' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/전자 부품, 컴퓨터/)).toBeInTheDocument();
    expect(screen.getByText(/기업코드 00126380/)).toBeInTheDocument();

    const detailCall = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .find((url) => /\/api\/companies\/00126380(\?|$)/.test(url));
    expect(detailCall).toBeDefined();
  });

  it('keeps the page usable when the detail API fails', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetchByUrl(() =>
        json(
          { success: false, error: { code: 'INTERNAL_ERROR', message: 'x' } },
          500,
        ),
      ),
    );

    renderPage();

    // 이름을 못 가져와도 제목 자리는 유지되고 다른 섹션은 정상 표시된다 (F-31)
    expect(
      await screen.findByRole('heading', { level: 1, name: '기업 분석' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: '2025년 핵심지표' }),
    ).toBeInTheDocument();
  });
});
