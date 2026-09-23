import { describe, expect, it } from 'vitest';
import type { CoverLetterInput } from './types';
import { findProblem, normalizeCharLimit } from './validate';

const letter = (over: Partial<CoverLetterInput> = {}): CoverLetterInput => ({
  title: '삼성전자 상반기',
  targetCompany: '삼성전자',
  targetPosition: '백엔드',
  jobContextId: null,
  items: [{ question: '지원 동기', answer: '저는', charLimit: 500 }],
  ...over,
});

describe('findProblem', () => {
  it('다 채운 자소서는 통과시킨다', () => {
    expect(findProblem(letter())).toBeNull();
  });

  it('빈 답변은 그 문항을 짚어서 막는다', () => {
    // 예전에는 그대로 서버로 가서 400 이 났고, 받는 자리에 catch 가 없어 아무 말도 안 떴다
    const problem = findProblem(letter({ items: [{ question: '지원 동기', answer: '  ', charLimit: 500 }] }));

    expect(problem).toEqual({ step: 1, message: expect.stringContaining('답변을 입력해 주세요') });
  });

  it('제한을 나중에 줄이면 이미 쓴 답변도 다시 본다', () => {
    /*
     * 입력칸의 maxLength 는 새로 치는 글자만 막는다. 500자로 써 둔 뒤 제한을 100 으로
     * 줄이면 답변은 그대로 남는데, 저장은 그대로 됐다.
     */
    const problem = findProblem(
      letter({ items: [{ question: '지원 동기', answer: 'ㄱ'.repeat(500), charLimit: 100 }] }),
    );

    expect(problem?.step).toBe(1);
    expect(problem?.message).toContain('400자 넘어요');
  });

  it('글자 수 제한이 비어 있으면(0) 막는다', () => {
    // 0 이면 답변 입력이 통째로 막히고, 서버도 받지 않는다
    const problem = findProblem(letter({ items: [{ question: '지원 동기', answer: '저는', charLimit: 0 }] }));

    expect(problem?.message).toContain('1~4000');
  });

  it('제목이 비었으면 첫 단계로 돌려보낸다', () => {
    expect(findProblem(letter({ title: '   ' }))).toEqual({
      step: 0,
      field: 'title',
      message: expect.stringContaining('제목'),
    });
  });

  it('서버가 받지 않는 길이는 보내기 전에 잡는다', () => {
    // 백엔드 @Size 와 같은 값이다. 넘겨 보내면 "요청 파라미터가 올바르지 않습니다" 만 돌아온다
    expect(findProblem(letter({ title: 'ㄱ'.repeat(121) }))?.message).toContain('120자');
    expect(
      findProblem(letter({ items: [{ question: 'ㄱ'.repeat(501), answer: '저는', charLimit: 500 }] }))?.message,
    ).toContain('500자');
  });

  it('공고에서 읽어 온 긴 회사명도 보내기 전에 잡는다', () => {
    // 회사명은 검색칸이 60자로 막지만, 공고를 읽어 채운 값은 길이 제한 없이 들어온다
    const problem = findProblem(letter({ targetCompany: 'ㄱ'.repeat(101) }));

    expect(problem?.step).toBe(0);
    expect(problem?.message).toContain('100자');
  });

  it('앞 문항부터 하나씩 짚는다', () => {
    const problem = findProblem(
      letter({
        items: [
          { question: '지원 동기', answer: '저는', charLimit: 500 },
          { question: '', answer: '', charLimit: 500 },
        ],
      }),
    );

    expect(problem?.step).toBe(2);
  });
});

describe('normalizeCharLimit', () => {
  it('앞에 붙은 0 을 떼고 숫자만 남긴다', () => {
    // 칸에는 "00…050" 이 그대로 남아 있고 제한만 50 이던 것이 이 문제였다
    expect(normalizeCharLimit('0000000000000000000000050')).toBe(50);
  });

  it('숫자가 아닌 글자는 버린다', () => {
    expect(normalizeCharLimit('5e3')).toBe(53);
    expect(normalizeCharLimit('-100')).toBe(100);
  });

  it('빈 칸은 비워 둔다', () => {
    // 지우는 도중에 1 로 되돌리면 글자를 지울 수가 없다
    expect(normalizeCharLimit('')).toBeNull();
    expect(normalizeCharLimit('abc')).toBeNull();
  });

  it('상한을 넘겨 적지 못한다', () => {
    expect(normalizeCharLimit('99999')).toBe(4000);
  });

  it('0 은 0 으로 둔다 — 막는 것은 저장 검증의 몫이다', () => {
    expect(normalizeCharLimit('0')).toBe(0);
  });
});
