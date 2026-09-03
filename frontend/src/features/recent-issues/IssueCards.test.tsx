import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { IssueDistributionCard } from './IssueDistributionCard';
import { IssueKpiRow } from './IssueKpiRow';
import { NewsFeedCard } from './NewsFeedCard';
import { TopNewsCard } from './TopNewsCard';
import type { NewsStats } from './types';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
const ok = (data: unknown) => json({ success: true, data });

const newsItem = (id: number, extra: Record<string, unknown> = {}) => ({
  id,
  title: `뉴스 ${id}`,
  description: `설명 ${id}`,
  publishedAt: '2025-05-13',
  originalUrl: `https://news.example.com/${id}`,
  ...extra,
});

describe('NewsFeedCard', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('lists news with a new-tab link, category chip only when present, and reports the latest date', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({
          items: [
            newsItem(1, { category: '투자', relatedBusiness: '파운드리', importanceScore: 9.2 }),
            newsItem(2, { description: null, publishedAt: '2025-05-12' }),
          ],
          total: 2,
        }),
      ),
    );
    const onLatestDate = vi.fn();

    render(<NewsFeedCard corpCode="00126380" onLatestDate={onLatestDate} />);

    const list = await screen.findByRole('list', { name: '뉴스 목록' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);

    const link = within(items[0]).getByRole('link', { name: /뉴스 1/ });
    expect(link).toHaveAttribute('href', 'https://news.example.com/1');
    expect(link).toHaveAttribute('target', '_blank');
    expect(within(items[0]).getByText('투자')).toBeInTheDocument();
    expect(within(items[0]).getByText('파운드리')).toBeInTheDocument();
    expect(within(items[0]).getByText('2025.05.13')).toBeInTheDocument();
    expect(within(items[1]).queryByText('설명 2')).not.toBeInTheDocument();
    expect(within(items[1]).queryByText(/중요도/)).not.toBeInTheDocument();
    expect(onLatestDate).toHaveBeenCalledWith('2025-05-13');
    expect(screen.queryByRole('button', { name: /더 많은 뉴스/ })).not.toBeInTheDocument();
  });

  it('appends the next page on 더 많은 뉴스 보기 and requests latest sort, size 6', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const page = new URL(String(input), 'http://x').searchParams.get('page');
      return Promise.resolve(
        ok({
          items: Array.from({ length: 6 }, (_, i) => newsItem((Number(page) - 1) * 6 + i + 1)),
          total: 13,
        }),
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<NewsFeedCard corpCode="A" />);
    await screen.findByRole('list', { name: '뉴스 목록' });

    const first = String(fetchMock.mock.calls[0][0]);
    expect(first).toContain('/api/companies/A/news?');
    expect(first).toContain('sort=latest');
    expect(first).toContain('page=1');
    expect(first).toContain('size=6');
    expect(first).not.toContain('category=');

    fireEvent.click(screen.getByRole('button', { name: /더 많은 뉴스 보기/ }));
    await waitFor(() =>
      expect(within(screen.getByRole('list', { name: '뉴스 목록' })).getAllByRole('listitem')).toHaveLength(12),
    );
    expect(String(fetchMock.mock.calls[1][0])).toContain('page=2');
    expect(screen.getByRole('button', { name: /더 많은 뉴스 보기/ })).toBeInTheDocument();
  });

  it('explains an empty list and offers retry on error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ items: [], total: 0 })));
    const first = render(<NewsFeedCard corpCode="A" />);
    expect(await screen.findByText('수집된 최근 뉴스가 없습니다')).toBeInTheDocument();
    first.unmount();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ success: false, error: { code: 'INTERNAL_ERROR', message: '오류' } }, 500))
      .mockResolvedValueOnce(ok({ items: [newsItem(9)], total: 1 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<NewsFeedCard corpCode="B" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('뉴스를 불러오지 못했습니다');
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(await screen.findByText(/뉴스 9/)).toBeInTheDocument();
  });
});

const stats: NewsStats = {
  kpis: {
    recentNewsCount: 48,
    recentNewsDays: 7,
    importantIssueCount: null,
    investmentIssueCount: 5,
    techIssueCount: 7,
    issueDays: 30,
  },
  distribution: {
    days: 30,
    total: 24,
    byCategory: [
      { category: '기술', count: 7, ratio: 29.2 },
      { category: '투자', count: 5, ratio: 20.8 },
      { category: '리스크', count: 4, ratio: null },
    ],
  },
};

describe('IssueKpiRow / IssueDistributionCard', () => {
  it('renders four KPI tiles with 미제공 for a missing count', () => {
    render(<IssueKpiRow state={{ status: 'success', data: stats }} />);

    const dl = screen.getByLabelText('뉴스 KPI');
    expect(within(dl).getByText('최근 뉴스 수')).toBeInTheDocument();
    expect(within(dl).getByText('48')).toBeInTheDocument();
    expect(within(dl).getByText('7일 기준')).toBeInTheDocument();
    expect(within(dl).getByText('미제공')).toBeInTheDocument();
  });

  it('draws one donut arc per category with the total in the middle', () => {
    render(<IssueDistributionCard onRetry={() => {}} state={{ status: 'success', data: stats }} />);

    expect(screen.getByRole('heading', { name: '이슈 분포' })).toBeInTheDocument();
    expect(document.querySelectorAll('[data-testid="donut-arc"]')).toHaveLength(3);
    expect(screen.getByText('24건')).toBeInTheDocument();
    const legend = within(screen.getByRole('list', { name: '카테고리별 이슈 분포' }));
    expect(legend.getByText('29.2%')).toBeInTheDocument();
    expect(legend.getByText('리스크')).toBeInTheDocument();
  });

  it('hides KPI and distribution on 404 and shows a retry notice for other errors', () => {
    const notFound = { status: 'error', error: new ApiError(404, 'UNKNOWN_ERROR', 'x') } as const;
    const { container, unmount } = render(
      <>
        <IssueKpiRow state={notFound} />
        <IssueDistributionCard onRetry={() => {}} state={notFound} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
    unmount();

    const onRetry = vi.fn();
    render(
      <IssueDistributionCard
        onRetry={onRetry}
        state={{ status: 'error', error: new ApiError(500, 'INTERNAL_ERROR', '서버') }}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('TopNewsCard', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders ranked items with category and importance, and hides when empty', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({
          items: [
            { rank: 1, id: 10250, title: '1위 뉴스', category: '실적', importanceScore: 9.6 },
            { rank: 2, id: 10241, title: '2위 뉴스' },
          ],
        }),
      ),
    );
    const first = render(<TopNewsCard corpCode="A" />);
    expect(await screen.findByRole('heading', { name: '중요 뉴스 TOP 2' })).toBeInTheDocument();
    expect(screen.getByText('1위 뉴스')).toBeInTheDocument();
    expect(screen.getByText('실적')).toBeInTheDocument();
    expect(screen.getByText('9.6')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    first.unmount();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ items: [] })));
    const second = render(<TopNewsCard corpCode="B" />);
    await waitFor(() => expect(second.container.querySelector('[role="status"]')).toBeNull());
    expect(second.container).toBeEmptyDOMElement();
  });
});
