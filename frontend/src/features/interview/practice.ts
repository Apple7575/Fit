import type { InterviewType, QuestionSource } from './types';

/**
 * "이 문항만 다시 연습하기" 로 넘어갈 때 들고 가는 것.
 *
 * <p>리포트를 읽고 나면 고칠 점은 알았는데 할 일이 없었다. 다섯 문항을 처음부터 다시 보는 것은
 * 부담이 크므로, 걸린 문항 하나만 2분 안에 다시 답해 보게 한다. 질문을 그대로 들고 가므로
 * 질문 생성 호출도 하지 않는다 (AI 한도를 태우지 않는다).
 */
export interface PracticeRequest {
  question: string;
  sourceType: QuestionSource;
  /** 어느 면접의 몇 번째 문항이었는지. 끝난 뒤 그 리포트로 돌아가는 데 쓴다 */
  fromInterviewId: number;
  fromNo: string;
  targetCompany: string | null;
  targetPosition: string | null;
  interviewType: InterviewType;
}

/** 라우터 state 에서 연습 요청을 꺼낸다. 직접 주소를 친 경우에는 없다 */
export function readPractice(state: unknown): PracticeRequest | null {
  if (!state || typeof state !== 'object') return null;
  const practice = (state as { practice?: unknown }).practice;
  if (!practice || typeof practice !== 'object') return null;
  const p = practice as Partial<PracticeRequest>;
  if (typeof p.question !== 'string' || p.question.length === 0) return null;
  if (typeof p.fromInterviewId !== 'number') return null;
  return {
    question: p.question,
    sourceType: p.sourceType ?? 'common',
    fromInterviewId: p.fromInterviewId,
    fromNo: p.fromNo ?? '',
    targetCompany: p.targetCompany ?? null,
    targetPosition: p.targetPosition ?? null,
    interviewType: p.interviewType ?? 'technical',
  };
}

/** 연습으로 만들어진 리포트에서 "돌아가기"를 띄우려고 넘기는 것 */
export interface PracticedFrom {
  interviewId: number;
  no: string;
}

export function readPracticedFrom(state: unknown): PracticedFrom | null {
  if (!state || typeof state !== 'object') return null;
  const from = (state as { practicedFrom?: unknown }).practicedFrom;
  if (!from || typeof from !== 'object') return null;
  const f = from as Partial<PracticedFrom>;
  if (typeof f.interviewId !== 'number') return null;
  return { interviewId: f.interviewId, no: f.no ?? '' };
}
