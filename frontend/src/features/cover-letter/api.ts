import { apiGet, apiSend } from '../../api/client';
import type {
  CoverLetter,
  CoverLetterInput,
  CoverLetterSummary,
  FeedbackRequest,
  ItemFeedback,
} from './types';

/** 문항 1개 AI 피드백(무저장, 공개). */
export const requestFeedback = (request: FeedbackRequest, signal?: AbortSignal) =>
  apiSend<ItemFeedback>('POST', '/api/cover-letters/feedback', request, { signal });

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
