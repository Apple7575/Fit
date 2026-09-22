import type { Company } from '../../types/company';
import { searchCompanies } from './api';
import { qwertyToHangul } from './qwertyToHangul';
import { corpNameOfAlias } from '../company-summary/companyName';
import { groupReading, hangulToRoman, romanToHangul } from './spelling';

/**
 * 같은 회사를 가리키는 다른 철자. 없으면 null.
 *
 * <p>아무 말이나 바꿔 보지는 않는다. 자판을 안 바꾸고 친 "tka" 도 영문이지만 그건 오타이지
 * 다른 철자가 아니다. 바꿀 만한 근거가 있을 때만 한 번 더 물어본다.
 */
function alternateSpelling(keyword: string): string | null {
  // 부르는 이름으로 쳤다면 공시명이 곧 다른 철자다 ("KT&G" → "케이티앤지")
  const byAlias = corpNameOfAlias(keyword);
  if (byAlias) return byAlias;

  const hasHangul = /[가-힣]/.test(keyword);
  const hasRoman = /[A-Za-z]/.test(keyword);

  // 한글과 영문이 섞였다 — 영문 쪽이 약어다 ("삼성SDS" → "삼성에스디에스")
  if (hasHangul && hasRoman) {
    const next = romanToHangul(keyword);
    return next === keyword ? null : next;
  }

  // 영문뿐이면 아는 그룹 이름일 때만 ("SK" → "에스케이"). 그래야 오타를 건드리지 않는다
  if (hasRoman) return groupReading(keyword);

  // 한글뿐이면 앞머리가 아는 그룹 이름일 때만 ("엘지화학" → "LG화학")
  if (hasHangul) {
    const next = hangulToRoman(keyword);
    return next === keyword ? null : next;
  }

  return null;
}

export interface SearchOutcome {
  items: Company[];
  total: number;
  /** 결과를 줄 세울 때 기준이 되는 말. 친 그대로 찾았으면 친 말 그대로다 */
  matched: string;
}

/** 같은 회사가 두 번 들어오지 않게 한다. 두 철자로 찾으면 겹치는 것이 나온다 */
function mergeUnique(groups: Company[][]): Company[] {
  const seen = new Set<string>();
  const merged: Company[] = [];
  for (const group of groups) {
    for (const company of group) {
      if (seen.has(company.corpCode)) continue;
      seen.add(company.corpCode);
      merged.push(company);
    }
  }
  return merged;
}

/**
 * 찾는 사람이 보고 싶어 할 순서로 줄 세운다.
 *
 * <p>서버는 이름 어느 자리에 있든 찾아 준다. "KT" 로 물으면 "디케이티" 도 같이 오는데,
 * 두 철자를 합치고 나면 정작 "케이티" 가 일곱 번째로 밀렸다. 이름이 통째로 같은 것을
 * 맨 앞에, 그다음 친 말로 시작하는 것, 그다음 다른 철자로 시작하는 것을 세운다.
 */
function rank(items: Company[], keywords: string[]): Company[] {
  const tierOf = (company: Company) => {
    if (keywords.some((word) => company.corpName === word)) return 0;
    const index = keywords.findIndex((word) => company.corpName.startsWith(word));
    return index === -1 ? keywords.length + 1 : index + 1;
  };
  // 같은 자리끼리는 받은 차례를 지킨다 (친 말의 결과가 앞에 온다)
  return [...items].sort((a, b) => tierOf(a) - tierOf(b));
}

/**
 * 철자가 갈리는 이름을 두 가지로 다 찾아 합친다.
 *
 * <p>DART 공시명은 한 그룹 안에서도 제각각이다 — "케이티", "케이티앤지" 옆에 "KT나스미디어",
 * "KTcs" 가 같이 있다. 그래서 "못 찾으면 그때 바꿔 본다" 로는 모자랐다. 친 말로 다섯 곳이
 * 잡히니 재시도를 하지 않았고, 다른 철자로 적힌 다섯 곳은 영영 보이지 않았다.
 *
 * <p>철자가 갈릴 수 있는 말이면 처음부터 두 가지로 찾아 합친다. 친 말의 결과가 늘 앞에 선다.
 *
 * <p>자판을 안 바꾸고 친 경우("tka" → "삼")는 성격이 다르다. 그건 잘못 친 것이지 다른
 * 철자가 아니므로, 친 말로 한 건도 못 찾았을 때만 되돌려 본다.
 */
export async function searchWithFallback(
  keyword: string,
  signal?: AbortSignal,
): Promise<SearchOutcome> {
  const alternate = alternateSpelling(keyword);

  const [typed, other] = await Promise.all([
    searchCompanies(keyword, signal),
    alternate ? searchCompanies(alternate, signal) : null,
  ]);

  if (typed.items.length > 0 || other) {
    const merged = mergeUnique([typed.items, other?.items ?? []]);
    if (merged.length > 0) {
      const items = rank(merged, alternate ? [keyword, alternate] : [keyword]);
      return { items, total: items.length, matched: keyword };
    }
  }

  // 여기까지 빈손이면 자판을 안 바꾸고 친 것으로 보고 한 번 더 되돌려 본다
  const hangul = qwertyToHangul(keyword);
  if (hangul !== keyword) {
    const retry = await searchCompanies(hangul, signal);
    if (retry.items.length > 0) return { ...retry, matched: hangul };
  }

  return { ...typed, matched: keyword };
}
