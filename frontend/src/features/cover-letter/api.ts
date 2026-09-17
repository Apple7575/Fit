import { apiGet, apiSend } from '../../api/client';
import type {
  CoverLetter,
  CoverLetterInput,
  CoverLetterSummary,
  JobPostingParseResult,
} from './types';

/** 채용공고 URL 에서 회사명과 모집 직무를 읽어 온다(무저장, 공개). */
export const parseJobPosting = (url: string, signal?: AbortSignal) =>
  apiSend<JobPostingParseResult>('POST', '/api/job-postings/parse', { url }, { signal });

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
