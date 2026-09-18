/** 마지막 글자가 받침 있는 한글이면 true. 한글이 아니면(영문·숫자) false 로 둔다 */
const hasFinalConsonant = (word: string): boolean => {
  const code = word.charCodeAt(word.length - 1);
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 !== 0;
};

/** 주격 조사: "수달이" · "여우가" */
export const withSubject = (word: string): string =>
  `${word}${hasFinalConsonant(word) ? '이' : '가'}`;
