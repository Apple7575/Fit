import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchComparisonTrends } from './api';
import type { CompanyTrend, IndustryCompany } from './types';

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
  return useApiQuery(`comparison-trends|${key}`, fetcher);
}
