/** 요약 칩: 키워드 → 신규 사업 순으로 중복 없이 최대 3개 */
export function pickSummaryChips(
  keywords: string[],
  newBusiness: string[],
  limit = 3,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of [...keywords, ...newBusiness]) {
    if (!seen.has(item)) {
      seen.add(item);
      out.push(item);
      if (out.length === limit) break;
    }
  }
  return out;
}
