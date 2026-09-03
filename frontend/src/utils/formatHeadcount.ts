/** 직원 순증감(명)을 부호 명시로 표기한다 (+4,015명 / -1,213명 / 0명) */
export const formatHeadcountChange = (n: number): string =>
  `${n > 0 ? '+' : ''}${n.toLocaleString('ko-KR')}명`;
