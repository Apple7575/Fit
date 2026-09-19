import { apiGet, apiSend } from '../../api/client';
import type {
  CoverLetter,
  CoverLetterInput,
  CoverLetterSummary,
  JobPostingContext,
  JobPostingParseResult,
} from './types';

/** 채용공고 URL 에서 회사명과 모집 직무를 읽어 온다(무저장, 공개). */
export const parseJobPosting = (url: string, signal?: AbortSignal) =>
  apiSend<JobPostingParseResult>('POST', '/api/job-postings/parse', { url }, { signal });

/**
 * 확인한 공고를 등록하고 검토 방에 붙일 식별자를 받는다.
 *
 * <p>회사명·직무명은 사용자가 화면에서 확정한 값을 보낸다. sourceKey 를 함께 주면 확인할 때
 * 긁어 둔 본문을 재사용해 공고를 다시 읽지 않는다.
 */
export const registerJobPosting = (
  url: string,
  companyName: string | null,
  positionName: string | null,
  sourceKey: string | null,
) =>
  apiSend<JobPostingContext>('POST', '/api/job-postings/contexts', {
    url,
    companyName,
    positionName,
    sourceKey,
  });

export const fetchCoverLetters = (signal?: AbortSignal) =>
  apiGet<CoverLetterSummary[]>('/api/cover-letters', { signal });

export const fetchCoverLetter = (id: number, signal?: AbortSignal) =>
  apiGet<CoverLetter>(`/api/cover-letters/${id}`, { signal });

export const createCoverLetter = (input: CoverLetterInput) =>
  apiSend<CoverLetter>('POST', '/api/cover-letters', input);

export const updateCoverLetter = (id: number, input: CoverLetterInput) =>
  apiSend<CoverLetter>('PUT', `/api/cover-letters/${id}`, input);

export async function deleteCoverLetter(id: number): Promise<void> {
  await apiSend<null>('DELETE', `/api/cover-letters/${id}`);
}
