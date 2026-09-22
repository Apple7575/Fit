import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import {
  fetchAllActivities,
  fetchEmployeeTrend,
  fetchFocus,
  fetchWorkforce,
} from './api';
import type {
  CompanyFocus,
  EmployeeTrendPoint,
  InvestmentActivity,
  WorkforceChange,
} from './types';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type ActivitiesState = QueryState<InvestmentActivity[]>;
export type WorkforceState = QueryState<WorkforceChange>;
export type FocusState = QueryState<CompanyFocus>;
export type EmployeeTrendState = QueryState<EmployeeTrendPoint[]>;

/** 네 유형의 투자 이벤트를 한 번에. corpCode 가 바뀌면 재조회, 진행 중 요청은 취소. */
export function useAllActivities(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchAllActivities(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`activities-all|${corpCode}`, fetcher, REUSE);
}

export function useWorkforce(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchWorkforce(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`workforce|${corpCode}`, fetcher, REUSE);
}

export function useFocus(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFocus(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`focus|${corpCode}`, fetcher, REUSE);
}

export function useEmployeeTrend(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchEmployeeTrend(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`employee-trend|${corpCode}`, fetcher, REUSE);
}
