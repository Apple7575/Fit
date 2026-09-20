import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchIndustryCompanies } from './api';
import type { IndustryCompany } from './types';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

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
  return useApiQuery(`industry-companies|${industryCode ?? ''}`, fetcher, REUSE);
}
