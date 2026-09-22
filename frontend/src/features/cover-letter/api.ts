import { apiGet, apiSend } from '../../api/client';
import type {
  CoverLetter,
  CoverLetterInput,
  CoverLetterSummary,
  JobPostingContext,
  JobPostingParseResult,
} from './types';

/**
 * 제목 없이 저장할 때 붙는 이름. 목록에서 "제목 없는 자소서" 들이 구분되지 않으므로
 * 좋은 이름은 아니지만, 이름 없는 자소서를 목록에 내보낼 수는 없다.
 */
export const UNTITLED_COVER_LETTER = '제목 없는 자소서';

/** 채용공고 URL 에서 회사명과 모집 직무를 읽어 온다(무저장, 공개). */
export const parseJobPosting = (url: string, signal?: AbortSignal) =>
  apiSend<JobPostingParseResult>('POST', '/api/job-postings/parse', { url }, { signal });

/**
 * 붙여넣은 공고 이미지에서 회사·직무를 읽어 온다.
 *
 * <p>본문이 이미지인데 그 주소가 서버가 받는 HTML 에 없어 주소로는 못 읽는 공고가 있다.
 * 화면에는 보이므로 복사해 온 이미지를 그대로 보낸다. 넣은 순서를 지킨다.
 */
export const parseJobPostingImages = (images: File[], signal?: AbortSignal) => {
  const form = new FormData();
  images.forEach((image) => form.append('files', image));
  return apiSend<JobPostingParseResult>('POST', '/api/job-postings/parse-images', form, { signal });
};

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
