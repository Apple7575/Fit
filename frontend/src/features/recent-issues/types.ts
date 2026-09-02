/** 목록 정렬 (명세: latest·importance) */
export type NewsSort = 'latest' | 'importance';

export const NEWS_SORT_LABELS: Record<NewsSort, string> = {
  latest: '최신순',
  importance: '중요도순',
};

/** 목록 페이지 크기 (명세 기본 6) */
export const NEWS_PAGE_SIZE = 6;
/** KPI 기간 (명세 기본 newsDays 7 · issueDays 30) */
export const NEWS_DAYS = 7;
export const ISSUE_DAYS = 30;

/**
 * 뉴스 한 건. 기본 필드(title·description·publishedAt·originalUrl)는 항상 오고,
 * AI 분류 결과(category·relatedBusiness·importanceScore)는 실패하면 null 이다.
 */
export interface NewsItem {
  id: number;
  title: string;
  description: string | null;
  /** YYYY-MM-DD */
  publishedAt: string | null;
  originalUrl: string | null;
  category: string | null;
  relatedBusiness: string | null;
  importanceScore: number | null;
}

export interface NewsPage {
  items: NewsItem[];
  total: number;
}

/** GET /news/stats 의 kpis + distribution */
export interface NewsStats {
  kpis: {
    recentNewsCount: number | null;
    recentNewsDays: number;
    importantIssueCount: number | null;
    investmentIssueCount: number | null;
    techIssueCount: number | null;
    issueDays: number;
  };
  distribution: {
    days: number;
    total: number | null;
    byCategory: Array<{ category: string; count: number; ratio: number | null }>;
  };
}

/** GET /news/top 의 items[] 한 건. id 는 /news 의 id 와 같다. */
export interface TopNewsItem {
  rank: number;
  id: number;
  title: string;
  category: string | null;
  importanceScore: number | null;
}
