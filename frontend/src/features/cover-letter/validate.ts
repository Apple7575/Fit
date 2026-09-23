import type { CoverLetterInput } from './types';

/**
 * 저장하기 전에 무엇이 잘못됐는지 먼저 본다.
 *
 * <p>여기가 없을 때는 잘못된 자소서가 그대로 서버로 갔다. 서버는 400 과 함께
 * "요청 파라미터가 올바르지 않습니다" 를 돌려주는데, 그 말로는 어느 문항의 무엇이
 * 문제인지 알 수 없다. 게다가 저장 함수에 catch 가 없어 그 400 조차 화면에 닿지
 * 못했다 — 사용자에게는 "저장을 눌렀는데 아무 일도 없다" 로만 보였다.
 *
 * <p>그래서 서버가 거절할 것을 프론트가 먼저 알고, 어느 칸인지 짚어서 말한다.
 * 아래 한계값은 백엔드 CoverLetterSaveRequest 의 제약과 같은 값이어야 한다.
 */
export const MAX_TITLE = 120;
export const MAX_POSITION = 120;
/** 공고 등록(JobPostingContextRequest)이 회사명을 100자까지만 받는다. 저장(120)보다 좁은 쪽에 맞춘다 */
export const MAX_COMPANY = 100;
export const MAX_QUESTION = 500;
/** 답변이 아무리 길어도 서버가 받지 않는 한계. 문항별 글자 수 제한과는 별개다 */
export const MAX_ANSWER = 4000;
/** 글자 수 제한 칸이 받는 범위. 0 을 허용하면 답변 입력이 통째로 막힌다 */
export const MIN_CHAR_LIMIT = 1;
export const MAX_CHAR_LIMIT = 4000;

export interface Problem {
  /** 이 문제가 있는 화면. 0 = 기업·직무, 1 이상 = 그 번째 문항 */
  step: number;
  message: string;
}

/**
 * 첫 번째 문제 하나만 돌려준다. 여러 개를 한꺼번에 늘어놓으면 어디부터 고칠지
 * 고르는 일이 사용자에게 넘어간다 — 한 번에 한 칸씩 짚어 주는 편이 빠르다.
 */
export function findProblem(input: CoverLetterInput): Problem | null {
  if (input.title.trim() === '') {
    return { step: 0, message: '자소서 제목을 입력해 주세요.' };
  }
  if (input.title.length > MAX_TITLE) {
    return { step: 0, message: `제목은 ${MAX_TITLE}자까지 쓸 수 있어요. 지금 ${input.title.length}자입니다.` };
  }
  if ((input.targetPosition?.length ?? 0) > MAX_POSITION) {
    return { step: 0, message: `지원 직무는 ${MAX_POSITION}자까지 쓸 수 있어요.` };
  }
  /*
   * 회사명은 사용자가 치면 검색칸이 60자로 막지만, 공고를 읽어 채운 값은 길이 제한 없이
   * 그대로 들어온다. 그 값이 길면 저장이나 공고 등록에서 400 이 나는데, 어느 칸 때문인지
   * 알 수 없다. 공고 등록 쪽이 더 좁으므로(100자) 그 값에 맞춘다.
   */
  if ((input.targetCompany?.length ?? 0) > MAX_COMPANY) {
    return { step: 0, message: `지원 회사는 ${MAX_COMPANY}자까지 쓸 수 있어요. 이름을 줄여 주세요.` };
  }

  for (const [index, item] of input.items.entries()) {
    const step = index + 1;
    const at = `문항 ${step}`;

    if (item.question.trim() === '') {
      return { step, message: `${at}의 질문을 입력해 주세요.` };
    }
    if (item.question.length > MAX_QUESTION) {
      return {
        step,
        message: `${at}의 질문은 ${MAX_QUESTION}자까지 쓸 수 있어요. 지금 ${item.question.length}자입니다.`,
      };
    }
    if (item.charLimit < MIN_CHAR_LIMIT || item.charLimit > MAX_CHAR_LIMIT) {
      return {
        step,
        message: `${at}의 글자 수 제한은 ${MIN_CHAR_LIMIT}~${MAX_CHAR_LIMIT} 사이로 정해 주세요.`,
      };
    }
    if (item.answer.trim() === '') {
      return { step, message: `${at}의 답변을 입력해 주세요. 빈 답변은 저장할 수 없어요.` };
    }
    /*
     * 제한을 나중에 줄인 경우가 여기로 온다. 입력칸의 maxLength 는 새로 치는 글자만
     * 막을 뿐, 이미 적혀 있던 글자는 손대지 않는다. 그래서 500자로 써 둔 답변이
     * 제한을 100자로 줄인 뒤에도 그대로 저장됐다.
     */
    if (item.answer.length > item.charLimit) {
      return {
        step,
        message: `${at}의 답변이 제한을 ${item.answer.length - item.charLimit}자 넘어요. (${item.answer.length} / ${item.charLimit}자)`,
      };
    }
    if (item.answer.length > MAX_ANSWER) {
      return { step, message: `${at}의 답변은 ${MAX_ANSWER}자까지 저장할 수 있어요.` };
    }
  }

  return null;
}

/**
 * 글자 수 제한 칸이 받은 글자를 숫자 하나로 정리한다.
 *
 * <p>"0000000000000000000000050" 을 넣으면 제한은 50 으로 걸리는데 칸에는 친 글자가
 * 그대로 남아 있었다. type="number" 인 입력칸을 React 가 느슨 비교로 맞추기 때문이다 —
 * 문자열 "00…050" 과 숫자 50 을 같다고 보아 DOM 을 다시 쓰지 않는다. 그래서 칸을
 * 글자로 받고, 받은 자리에서 숫자만 남긴다.
 *
 * <p>빈 칸은 null 이다. 지우는 도중에 1 로 되돌리면 글자를 지울 수가 없다.
 */
export function normalizeCharLimit(typed: string): number | null {
  const digits = typed.replace(/\D/g, '').replace(/^0+(?=\d)/, '');
  if (digits === '') return null;
  return Math.min(MAX_CHAR_LIMIT, Number(digits));
}
