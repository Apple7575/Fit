import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
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
  return useApiQuery(`activities-all|${corpCode}`, fetcher);
}

export function useWorkforce(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchWorkforce(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`workforce|${corpCode}`, fetcher);
}

export function useFocus(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFocus(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`focus|${corpCode}`, fetcher);
}

export function useEmployeeTrend(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchEmployeeTrend(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`employee-trend|${corpCode}`, fetcher);
}
