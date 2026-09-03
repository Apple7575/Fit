import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchIndustryCompanies } from './api';
import type { IndustryCompany } from './types';

export type IndustryCompaniesState = QueryState<IndustryCompany[]>;

/**
 * 비교 후보 기업 목록. industryCode 가 아직 없으면(기본정보 미도착) 빈 목록으로 즉시 성공 처리한다.
 */
export function useIndustryCompanies(industryCode: string | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      industryCode
        ? fetchIndustryCompanies(industryCode, signal)
        : Promise.resolve<IndustryCompany[]>([]),
    [industryCode],
  );
  return useApiQuery(`industry-companies|${industryCode ?? ''}`, fetcher);
}
