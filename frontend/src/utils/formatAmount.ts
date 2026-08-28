const JO = 1_0000_0000_0000; // 1조
const EOK = 1_0000_0000; // 1억
const MAN = 1_0000; // 1만

const withComma = (n: number) => n.toLocaleString('ko-KR');

/**
 * 원 단위 금액을 읽기 쉬운 한국식 단위(조·억·만)로 표기한다.
 * 예) 300_870_903_000_000 → "300조 8,709억"
 * 단위 문자 "원"은 붙이지 않는다 (표시 쪽에서 붙임).
 */
export function formatAmount(amount: number): string {
  if (amount === 0) {
    return '0';
  }

  const sign = amount < 0 ? '-' : '';
  const abs = Math.abs(amount);

  if (abs >= JO) {
    const jo = Math.floor(abs / JO);
    const eok = Math.round((abs % JO) / EOK);
    return eok > 0
      ? `${sign}${withComma(jo)}조 ${withComma(eok)}억`
      : `${sign}${withComma(jo)}조`;
  }

  if (abs >= EOK) {
    return `${sign}${withComma(Math.round(abs / EOK))}억`;
  }

  if (abs >= MAN) {
    return `${sign}${withComma(Math.round(abs / MAN))}만`;
  }

  return `${sign}${withComma(abs)}`;
}
