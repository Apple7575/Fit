import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchNews, fetchNewsStats, fetchTopNews, toNewsPage, toNewsStats, toTopNews } from './api';

describe('toNewsPage', () => {
  it('keeps basic fields and nulls missing AI fields', () => {
    const page = toNewsPage({
      items: [
        {
          id: 1,
          title: '제목',
          description: '',
          publishedAt: '2025-05-13',
          originalUrl: 'https://x',
        },
      ],
      total: 48,
    });

    expect(page.total).toBe(48);
    expect(page.items[0]).toEqual({
      id: 1,
      title: '제목',
      description: null,
      publishedAt: '2025-05-13',
      originalUrl: 'https://x',
      category: null,
      relatedBusiness: null,
      importanceScore: null,
    });
  });

  it('falls back to the item count when total is missing', () => {
    expect(toNewsPage({ items: [{ id: 1, title: 'a' }] }).total).toBe(1);
    expect(toNewsPage({})).toEqual({ items: [], total: 0 });
  });
});

describe('toNewsStats', () => {
  it('fills defaults and nulls for a partial response', () => {
    const stats = toNewsStats({ kpis: { recentNewsCount: 3 }, distribution: null });

    expect(stats.kpis).toEqual({
      recentNewsCount: 3,
      recentNewsDays: 7,
      importantIssueCount: null,
      investmentIssueCount: null,
      techIssueCount: null,
      issueDays: 30,
    });
    expect(stats.distribution).toEqual({ days: 30, total: null, byCategory: [] });
  });
});

describe('toTopNews', () => {
  it('sorts by rank and nulls missing AI fields', () => {
    expect(
      toTopNews({
        items: [
          { rank: 2, id: 2, title: 'b' },
          { rank: 1, id: 1, title: 'a', category: '투자', importanceScore: 9.2 },
        ],
      }),
    ).toEqual([
      { rank: 1, id: 1, title: 'a', category: '투자', importanceScore: 9.2 },
      { rank: 2, id: 2, title: 'b', category: null, importanceScore: null },
    ]);
  });
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('recent-issues fetchers (실 API 경로 · 백엔드 CompanyNewsController 계약)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('fetchNewsStats 는 newsDays=7 · issueDays=30 을 보내고 AI 미분석 KPI 를 null 로 유지한다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({
        success: true,
        data: {
          kpis: {
            recentNewsCount: 12,
            recentNewsDays: 7,
            importantIssueCount: null,
            investmentIssueCount: null,
            techIssueCount: null,
            issueDays: 30,
          },
          distribution: { days: 30, total: null, byCategory: [] },
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const stats = await fetchNewsStats('00126380');

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://x');
    expect(url.pathname).toBe('/api/companies/00126380/news/stats');
    expect(url.searchParams.get('newsDays')).toBe('7');
    expect(url.searchParams.get('issueDays')).toBe('30');
    expect(url.searchParams.has('days')).toBe(false);
    expect(stats.kpis.recentNewsCount).toBe(12);
    expect(stats.kpis.importantIssueCount).toBeNull();
    expect(stats.distribution).toEqual({ days: 30, total: null, byCategory: [] });
  });

  it('fetchTopNews 는 days=30 · limit=3 을 보내고 빈 목록을 그대로 돌려준다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ success: true, data: { items: [] } }));
    vi.stubGlobal('fetch', fetchMock);

    const items = await fetchTopNews('00126380');

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://x');
    expect(url.pathname).toBe('/api/companies/00126380/news/top');
    expect(url.searchParams.get('days')).toBe('30');
    expect(url.searchParams.get('limit')).toBe('3');
    expect(items).toEqual([]);
  });

  it('fetchNews 는 category 가 있을 때만 파라미터로 보내고 days=7 을 붙인다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ success: true, data: { items: [], total: 0 } }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchNews('00126380', { category: '투자', sort: 'importance', page: 2 });

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://x');
    expect(url.pathname).toBe('/api/companies/00126380/news');
    expect(url.searchParams.get('category')).toBe('투자');
    expect(url.searchParams.get('sort')).toBe('importance');
    expect(url.searchParams.get('page')).toBe('2');
    expect(url.searchParams.get('size')).toBe('6');
    expect(url.searchParams.get('days')).toBe('7');
  });

  it('404 는 ApiError(COMPANY_NOT_FOUND) 로 던진다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        json({ success: false, error: { code: 'COMPANY_NOT_FOUND', message: '없음' } }, 404),
      ),
    );

    await expect(fetchNewsStats('99999999')).rejects.toMatchObject({
      status: 404,
      code: 'COMPANY_NOT_FOUND',
    });
  });
});
