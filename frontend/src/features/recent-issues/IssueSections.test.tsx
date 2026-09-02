import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { NewsListSection } from './NewsListSection';
import { NewsStatsSection } from './NewsStatsSection';
import { TopNewsSection } from './TopNewsSection';
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

describe('NewsListSection', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('lists news with a new-tab link and shows AI fields only when present', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        ok({
          items: [
            newsItem(1, { category: '투자', relatedBusiness: '파운드리', importanceScore: 9.2 }),
            newsItem(2, { description: null }),
          ],
          total: 2,
        }),
      ),
    );

    render(<NewsListSection corpCode="00126380" />);

    const list = await screen.findByRole('list', { name: '뉴스 목록' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);

    const link = within(items[0]).getByRole('link', { name: /뉴스 1/ });
    expect(link).toHaveAttribute('href', 'https://news.example.com/1');
    expect(link).toHaveAttribute('target', '_blank');
    expect(within(items[0]).getByText('투자')).toBeInTheDocument();
    expect(within(items[0]).getByText('파운드리')).toBeInTheDocument();
    expect(within(items[0]).getByText('중요도 9.2')).toBeInTheDocument();
    expect(within(items[0]).getByText('2025.05.13')).toBeInTheDocument();

    expect(within(items[1]).queryByText(/중요도/)).not.toBeInTheDocument();
    expect(within(items[1]).queryByText('설명 2')).not.toBeInTheDocument();
    expect(screen.getByText(/총 2건/)).toBeInTheDocument();
  });

  it('requests page 1 with latest sort and refetches on sort, category and page changes', async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        ok({ items: Array.from({ length: 6 }, (_, i) => newsItem(i + 1)), total: 13 }),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<NewsListSection categories={['투자', '기술']} corpCode="A" />);
    await screen.findByRole('list', { name: '뉴스 목록' });

    const first = String(fetchMock.mock.calls[0][0]);
    expect(first).toContain('/api/companies/A/news?');
    expect(first).toContain('sort=latest');
    expect(first).toContain('page=1');
    expect(first).toContain('size=6');
    expect(first).not.toContain('category=');

    fireEvent.click(screen.getByRole('radio', { name: '중요도순' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toContain('sort=importance');

    fireEvent.click(screen.getByRole('radio', { name: '기술' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(String(fetchMock.mock.calls[2][0])).toContain('category=%EA%B8%B0%EC%88%A0');

    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '다음' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(String(fetchMock.mock.calls[3][0])).toContain('page=2');
  });

  it('explains an empty list and offers retry on error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ items: [], total: 0 })));
    const first = render(<NewsListSection corpCode="A" />);
    expect(await screen.findByText('수집된 최근 뉴스가 없습니다')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '뉴스 페이지' })).not.toBeInTheDocument();
    first.unmount();

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        json({ success: false, error: { code: 'INTERNAL_ERROR', message: '오류' } }, 500),
      )
      .mockResolvedValueOnce(ok({ items: [newsItem(9)], total: 1 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<NewsListSection corpCode="B" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('뉴스를 불러오지 못했습니다');
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(await screen.findByText(/뉴스 9/)).toBeInTheDocument();
  });
});

describe('NewsStatsSection', () => {
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
      total: 96,
      byCategory: [
        { category: '기술', count: 28, ratio: 29.2 },
        { category: '투자', count: 20, ratio: null },
      ],
    },
  };

  it('renders KPI tiles with 미제공 for missing counts and the category distribution', () => {
    render(<NewsStatsSection onRetry={() => {}} state={{ status: 'success', data: stats }} />);

    expect(screen.getByText('최근 7일 뉴스')).toBeInTheDocument();
    expect(screen.getByText('48건')).toBeInTheDocument();
    expect(screen.getByText('미제공')).toBeInTheDocument();

    const dist = screen.getByRole('list', { name: '카테고리별 이슈 분포' });
    expect(within(dist).getAllByRole('listitem')).toHaveLength(2);
    expect(within(dist).getByText('28건 · 29.2%')).toBeInTheDocument();
    expect(within(dist).getByText('20건')).toBeInTheDocument();
  });

  it('hides itself on 404 and shows a retry notice on other errors', () => {
    const { container, unmount } = render(
      <NewsStatsSection
        onRetry={() => {}}
        state={{ status: 'error', error: new ApiError(404, 'UNKNOWN_ERROR', 'x') }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
    unmount();

    const onRetry = vi.fn();
    render(
      <NewsStatsSection
        onRetry={onRetry}
        state={{ status: 'error', error: new ApiError(500, 'INTERNAL_ERROR', '서버') }}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('TopNewsSection', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders ranked items and hides when empty', async () => {
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
    const first = render(<TopNewsSection corpCode="A" />);
    expect(await screen.findByRole('heading', { name: '중요 뉴스 TOP 2' })).toBeInTheDocument();
    expect(screen.getByText('1위 뉴스')).toBeInTheDocument();
    expect(screen.getByText('중요도 9.6')).toBeInTheDocument();
    first.unmount();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ items: [] })));
    const second = render(<TopNewsSection corpCode="B" />);
    await waitFor(() => expect(second.container.querySelector('[role="status"]')).toBeNull());
    expect(second.container).toBeEmptyDOMElement();
  });
});
