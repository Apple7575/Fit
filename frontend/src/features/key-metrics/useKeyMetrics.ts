import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import type { KeyMetricsData } from '../../types/metrics';
import { fetchKeyMetrics } from './api';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type KeyMetricsState = QueryState<KeyMetricsData>;

/** corpCode·year 가 바뀌면 자동 재조회. year 가 없으면 서버 기본(최신 연도). 진행 중 요청은 취소한다. */
export function useKeyMetrics(corpCode: string, year?: number | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchKeyMetrics(corpCode, year, signal),
    [corpCode, year],
  );
  return useApiQuery(`key-metrics|${corpCode}|${year ?? 'latest'}`, fetcher, REUSE);
}
