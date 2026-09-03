import { ApiError, apiGet } from '../../api/client';
import {
  mockNewsByCompany,
  mockNewsStatsByCompany,
  mockTopNewsByCompany,
} from '../../mocks/recentIssues';
import {
  ISSUE_DAYS,
  NEWS_DAYS,
  NEWS_PAGE_SIZE,
  type NewsItem,
  type NewsPage,
  type NewsSort,
  type NewsStats,
  type TopNewsItem,
} from './types';

/** GET /news 의 data */
export interface NewsResponse {
  items?: Array<{
    id: number;
    title: string;
    description?: string | null;
    publishedAt?: string | null;
    originalUrl?: string | null;
    category?: string | null;
    relatedBusiness?: string | null;
    importanceScore?: number | null;
  }>;
  total?: number;
}

/** GET /news/stats 의 data */
export interface NewsStatsResponse {
  kpis?: Partial<NewsStats['kpis']> | null;
  distribution?: {
    days?: number;
    total?: number | null;
    byCategory?: Array<{ category: string; count: number; ratio?: number | null }>;
  } | null;
}

/** GET /news/top 의 data */
export interface TopNewsResponse {
  items?: Array<{
    rank: number;
    id: number;
    title: string;
    category?: string | null;
    importanceScore?: number | null;
  }>;
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
const str = (v: unknown): string | null =>
  typeof v === 'string' && v.trim() !== '' ? v : null;

/** 기본 필드는 있는 그대로, AI 필드는 없으면 null — AI 실패에도 기본 뉴스는 그린다. */
export const toNewsPage = (response: NewsResponse): NewsPage => {
  const items: NewsItem[] = (response.items ?? []).map((item) => ({
    id: item.id,
    title: item.title,
    description: str(item.description),
    publishedAt: str(item.publishedAt),
    originalUrl: str(item.originalUrl),
    category: str(item.category),
    relatedBusiness: str(item.relatedBusiness),
    importanceScore: num(item.importanceScore),
  }));
  return { items, total: typeof response.total === 'number' ? response.total : items.length };
};

export const toNewsStats = (response: NewsStatsResponse): NewsStats => {
  const k = response.kpis ?? {};
  const d = response.distribution ?? {};
  return {
    kpis: {
      recentNewsCount: num(k.recentNewsCount),
      recentNewsDays: k.recentNewsDays ?? NEWS_DAYS,
      importantIssueCount: num(k.importantIssueCount),
      investmentIssueCount: num(k.investmentIssueCount),
      techIssueCount: num(k.techIssueCount),
      issueDays: k.issueDays ?? ISSUE_DAYS,
    },
    distribution: {
      days: d.days ?? ISSUE_DAYS,
      total: num(d.total),
      byCategory: (d.byCategory ?? []).map((c) => ({
        category: c.category,
        count: c.count,
        ratio: num(c.ratio),
      })),
    },
  };
};

export const toTopNews = (response: TopNewsResponse): TopNewsItem[] =>
  (response.items ?? [])
    .map((item) => ({
      rank: item.rank,
      id: item.id,
      title: item.title,
      category: str(item.category),
      importanceScore: num(item.importanceScore),
    }))
    .sort((a, b) => a.rank - b.rank);

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const notFound = () =>
  new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');

export interface NewsQuery {
  /** null 이면 전체 */
  category: string | null;
  sort: NewsSort;
  /** 1부터 */
  page: number;
}

export async function fetchNews(
  corpCode: string,
  query: NewsQuery,
  signal?: AbortSignal,
): Promise<NewsPage> {
  if (isMockEnabled()) {
    await delay(300);
    const all = mockNewsByCompany[corpCode];
    if (!all) throw notFound();
    const filtered = all.filter(
      (n) => query.category === null || n.category === query.category,
    );
    const sorted = [...filtered].sort((a, b) =>
      query.sort === 'importance'
        ? (b.importanceScore ?? -1) - (a.importanceScore ?? -1)
        : (b.publishedAt ?? '').localeCompare(a.publishedAt ?? ''),
    );
    const start = (query.page - 1) * NEWS_PAGE_SIZE;
    return {
      items: sorted.slice(start, start + NEWS_PAGE_SIZE),
      total: sorted.length,
    };
  }

  const params = new URLSearchParams({
    days: String(NEWS_DAYS),
    sort: query.sort,
    page: String(query.page),
    size: String(NEWS_PAGE_SIZE),
  });
  if (query.category) params.set('category', query.category);
  const data = await apiGet<NewsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/news?${params}`,
    { signal },
  );
  return toNewsPage(data);
}

export async function fetchNewsStats(
  corpCode: string,
  signal?: AbortSignal,
): Promise<NewsStats> {
  if (isMockEnabled()) {
    await delay(300);
    const stats = mockNewsStatsByCompany[corpCode];
    if (!stats) throw notFound();
    return stats;
  }

  const params = new URLSearchParams({
    newsDays: String(NEWS_DAYS),
    issueDays: String(ISSUE_DAYS),
  });
  const data = await apiGet<NewsStatsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/news/stats?${params}`,
    { signal },
  );
  return toNewsStats(data);
}

export async function fetchTopNews(
  corpCode: string,
  signal?: AbortSignal,
): Promise<TopNewsItem[]> {
  if (isMockEnabled()) {
    await delay(300);
    const top = mockTopNewsByCompany[corpCode];
    if (!top) throw notFound();
    return top;
  }

  const params = new URLSearchParams({ days: String(ISSUE_DAYS), limit: '3' });
  const data = await apiGet<TopNewsResponse>(
    `/api/companies/${encodeURIComponent(corpCode)}/news/top?${params}`,
    { signal },
  );
  return toTopNews(data);
}
