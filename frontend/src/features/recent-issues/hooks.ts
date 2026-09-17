import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchNews, fetchNewsStats, fetchTopNews, type NewsQuery } from './api';

/** corpCode·카테고리·정렬·페이지가 바뀌면 목록을 다시 조회한다. 진행 중 요청은 취소. */
export function useNews(corpCode: string, query: NewsQuery) {
  const { category, sort, page } = query;
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchNews(corpCode, { category, sort, page }, signal),
    [corpCode, category, sort, page],
  );
  return useApiQuery(
    `news|${corpCode}|${category ?? ''}|${sort}|${page}`,
    fetcher,
  );
}

export function useNewsStats(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchNewsStats(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`news-stats|${corpCode}`, fetcher);
}

export function useTopNews(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchTopNews(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`news-top|${corpCode}`, fetcher);
}
