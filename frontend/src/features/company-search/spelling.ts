/**
 * 기업명의 두 가지 철자를 오간다 ("삼성SDS" ↔ "삼성에스디에스", "엘지화학" ↔ "LG화학").
 *
 * <p>DART 공시명이 통용명과 늘 같지는 않고, 한 그룹 안에서도 제각각이다.
 *
 * <pre>
 *   LG 계열   → LG전자, LG화학   (영문)  … 다만 LG씨엔에스는 한글
 *   SK 계열   → SK하이닉스       (영문)  … 다만 에스케이바이오팜은 한글
 *   KT 계열   → 케이티, 케이티앤지 (한글) … 동시에 KT나스미디어, KTcs 도 있다
 * </pre>
 *
 * <p>어느 쪽으로 적혀 있는지 사람이 알 방법이 없다. 그래서 두 철자를 모두 찾아 합쳐 준다.
 */

/** 영문 한 글자를 읽는 법. 기업명에 쓰이는 방식(에스디에스, 씨엔에스)을 따른다 */
const READING: Record<string, string> = {
  a: '에이',
  b: '비',
  c: '씨',
  d: '디',
  e: '이',
  f: '에프',
  g: '지',
  h: '에이치',
  i: '아이',
  j: '제이',
  k: '케이',
  l: '엘',
  m: '엠',
  n: '엔',
  o: '오',
  p: '피',
  q: '큐',
  r: '알',
  s: '에스',
  t: '티',
  u: '유',
  v: '브이',
  w: '더블유',
  x: '엑스',
  y: '와이',
  z: '제트',
};

/**
 * 통째로 읽는 그룹 이름. 한 글자씩 읽으면 실제 공시명과 달라진다
 * ("LG" 는 "엘지" 지 "엘아이" 가 아니다).
 */
const GROUP: Record<string, string> = {
  lg: '엘지',
  sk: '에스케이',
  kt: '케이티',
  cj: '씨제이',
  gs: '지에스',
  ls: '엘에스',
  hd: '에이치디',
  kb: '케이비',
  nh: '엔에이치',
  db: '디비',
  bnk: '비엔케이',
  dgb: '디지비',
  jb: '제이비',
};

/** 한글 그룹 이름 → 영문. 긴 것부터 맞춰야 "에스케이" 가 "에스"+"케이" 로 쪼개지지 않는다 */
const GROUP_BACK = Object.entries(GROUP)
  .map(([roman, hangul]) => [hangul, roman.toUpperCase()] as const)
  .sort((a, b) => b[0].length - a[0].length);

/** 통째로 읽는 그룹 이름이면 그 한글 음차를 돌려준다 ("SK" → "에스케이"). 아니면 null */
export function groupReading(roman: string): string | null {
  return GROUP[roman.trim().toLowerCase()] ?? null;
}

/**
 * 영문을 한글 음차로 ("삼성SDS" → "삼성에스디에스").
 *
 * <p>영문은 어디에 있든 바꿔도 안전하다 — 한글 사이에 낀 알파벳은 읽는 법이 하나뿐이다.
 */
export function romanToHangul(keyword: string): string {
  if (!/[A-Za-z]/.test(keyword)) return keyword;

  return keyword.replace(/[A-Za-z]+/g, (chunk) => {
    const lower = chunk.toLowerCase();
    return GROUP[lower] ?? [...lower].map((letter) => READING[letter] ?? letter).join('');
  });
}

/**
 * 한글 그룹 이름을 영문으로 ("엘지화학" → "LG화학").
 *
 * <p>반대 방향은 맨 앞의 그룹 이름만 바꾼다. 한글은 글자마다 읽는 법이 겹쳐서, 한 글자씩
 * 되돌리면 멀쩡한 이름이 망가진다 — "엘지이노텍" 의 "이" 를 E 로 보면 "LGE노텍" 이 된다.
 */
export function hangulToRoman(keyword: string): string {
  for (const [hangul, roman] of GROUP_BACK) {
    if (keyword.startsWith(hangul)) return roman + keyword.slice(hangul.length);
  }
  return keyword;
}
