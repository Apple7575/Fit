import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchComparisonTrends } from './api';
import type { CompanyTrend, IndustryCompany } from './types';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type ComparisonTrendsState = QueryState<CompanyTrend[]>;

/**
 * 선택된 기업(조회 기업 + peers)의 5개년 지표를 한꺼번에 조회한다.
 * 기업 목록이 바뀌면 재조회, 진행 중 요청은 취소. 결과 순서는 입력 순서와 같다.
 */
export function useComparisonTrends(companies: IndustryCompany[]) {
  const key = companies.map((c) => `${c.corpCode}:${c.corpName}`).join('|');
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      fetchComparisonTrends(
        key
          ? key.split('|').map((pair) => {
              const [corpCode, corpName] = pair.split(':');
              return { corpCode, corpName };
            })
          : [],
        signal,
      ),
    [key],
  );
  /*
   * 맨 앞은 늘 조회 기업이고 그 뒤가 비교 기업이다. 비교 기업만 바뀌는 동안에는 보던
   * 그래프를 지운다 — 다른 기업으로 옮기면 맨 앞이 바뀌므로 저절로 버려진다.
   */
  return useApiQuery(`comparison-trends|${key}`, fetcher, {
    ...REUSE,
    keepPreviousWhile: companies[0]?.corpCode,
  });
}
