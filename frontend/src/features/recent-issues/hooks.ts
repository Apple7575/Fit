import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery } from '../../hooks/useApiQuery';
import { fetchNews, fetchNewsStats, fetchTopNews, type NewsQuery } from './api';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

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
    REUSE,
  );
}

export function useNewsStats(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchNewsStats(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`news-stats|${corpCode}`, fetcher, REUSE);
}

export function useTopNews(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchTopNews(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`news-top|${corpCode}`, fetcher, REUSE);
}
