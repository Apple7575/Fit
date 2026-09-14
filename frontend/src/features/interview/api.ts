import { apiGet, apiSend } from '../../api/client';
import type {
  AnalyzeRequest,
  AnalyzeResult,
  Followup,
  FollowupRequest,
  GeneratedQuestion,
  Interview,
  InterviewSaveInput,
  InterviewSummary,
  QuestionGenerateRequest,
} from './types';

/** 면접 질문 생성(무저장, 로그인 전용). */
export const generateQuestions = (request: QuestionGenerateRequest, signal?: AbortSignal) =>
  apiSend<{ questions: GeneratedQuestion[] }>('POST', '/api/interviews/questions', request, { signal });

/** 답변 일괄 분석(무저장). */
export const analyzeAnswers = (request: AnalyzeRequest, signal?: AbortSignal) =>
  apiSend<AnalyzeResult>('POST', '/api/interviews/analyze', request, { signal });

/** 직전 답변 기반 꼬리질문(무저장). */
export const requestFollowup = (request: FollowupRequest, signal?: AbortSignal) =>
  apiSend<Followup>('POST', '/api/interviews/followup', request, { signal });

export const fetchInterviews = (signal?: AbortSignal) =>
  apiGet<InterviewSummary[]>('/api/interviews', { signal });

export const fetchInterview = (id: number, signal?: AbortSignal) =>
  apiGet<Interview>(`/api/interviews/${id}`, { signal });

export const createInterview = (input: InterviewSaveInput) =>
  apiSend<Interview>('POST', '/api/interviews', input);

export async function deleteInterview(id: number): Promise<void> {
  await apiSend<null>('DELETE', `/api/interviews/${id}`);
}
