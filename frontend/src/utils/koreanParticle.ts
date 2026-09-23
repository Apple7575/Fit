/** 마지막 글자가 받침 있는 한글이면 true. 한글이 아니면(영문·숫자) false 로 둔다 */
const hasFinalConsonant = (word: string): boolean => {
  const code = word.charCodeAt(word.length - 1);
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 !== 0;
};

/** 주격 조사: "수달이" · "여우가" */
export const withSubject = (word: string): string =>
  `${word}${hasFinalConsonant(word) ? '이' : '가'}`;

/** 마지막 글자의 받침이 ㄹ 인지. 'ㄹ' 받침은 '으로'가 아니라 '로'를 쓴다 */
const endsWithRieul = (word: string): boolean => {
  const code = word.charCodeAt(word.length - 1);
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 === 8;
};

/** 목적격 조사: "가전을" · "반도체를" */
export const withObject = (word: string): string =>
  `${word}${hasFinalConsonant(word) ? '을' : '를'}`;

/**
 * 수단·자격 조사: "반도체로" · "스마트폰으로" · "건설로".
 *
 * <p>받침이 없으면 '로', 있으면 '으로'인데 ㄹ 받침만 예외로 '로'를 쓴다.
 * 영문·숫자로 끝나면 받침이 없는 것으로 보고 '로'를 붙인다("EV로", "IT기기로").
 */
export const withInstrumental = (word: string): string =>
  `${word}${hasFinalConsonant(word) && !endsWithRieul(word) ? '으로' : '로'}`;
