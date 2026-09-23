import type { KeyMetricsData } from '../../types/metrics';
import { formatMetricCompact } from '../../utils/formatMetric';
import { withInstrumental, withObject } from '../../utils/koreanParticle';
import type { CompanyProfile } from '../company-profile/types';
import type { CompanyFocus } from '../focus-areas/types';
import { TAGLINE_OVERRIDE } from './taglineOverride';

/**
 * 첫 화면의 한 줄. "반도체 · 스마트폰 · 가전으로 333.6조 원을 버는 회사".
 * 무엇으로(키워드 → 사업부 → 제품 순으로 찾는다) + 얼마나(매출). 둘 다 없으면 null.
 * 판정 없이 데이터에 있는 말만 조합한다.
 *
 * <p>조사는 앞 낱말의 받침을 보고 고른다. 붙박이로 "로"를 쓰면 "스마트폰로"가 된다.
 */
export function buildTagline(
  profile: CompanyProfile | null,
  focus: CompanyFocus | null,
  metrics: KeyMetricsData | null,
  /** 회사 이름. 같은 말이 키워드에 들어 있으면 빼기 위해 쓴다 ("네이버 · 광고 · 커머스") */
  corpName?: string | null,
  /** DART 고유번호. 손으로 정해 둔 낱말이 있는 회사인지 가리는 데 쓴다 */
  corpCode?: string | null,
): string | null {
  const what = pickWhat(profile, focus, corpName, corpCode);
  const revenue = metrics?.metrics.find((m) => m.key === 'revenue')?.value ?? null;

  if (what.length > 0 && revenue !== null) {
    return `${withInstrumental(what.join(' · '))} ${formatMetricCompact('KRW', revenue)} 원을 버는 회사`;
  }
  if (what.length > 0) return `${withObject(what.join(' · '))} 하는 회사`;
  if (revenue !== null) return `한 해 매출 ${formatMetricCompact('KRW', revenue)} 원의 회사`;
  return null;
}

/**
 * 회사 이름을 그대로 되풀이하는 키워드인지. 한 줄 설명에서 아무것도 알려주지 않는다.
 *
 * <p>딱 같을 때만 뺀다. "들어 있으면 뺀다"로 하면 카카오의 "카카오톡"처럼 이름을 품은
 * 진짜 제품까지 사라진다 — 그건 오히려 가장 좋은 키워드다.
 *
 * <p>표기가 다른 경우(회사명 "NAVER", 키워드 "네이버")는 여기서 걸러지지 않는다. 표기를
 * 옮겨 맞추기 시작하면 틀리는 쪽이 더 많아져, 그 몫은 키워드를 만드는 쪽에 남겨 둔다.
 */
const sameAsName = (keyword: string, name: string | null | undefined): boolean => {
  if (!name) return false;
  const norm = (v: string) => v.replace(/\s+/g, '').toLowerCase();
  return norm(keyword) === norm(name);
};

function pickWhat(
  profile: CompanyProfile | null,
  focus: CompanyFocus | null,
  corpName?: string | null,
  corpCode?: string | null,
): string[] {
  // 손으로 정해 둔 회사는 그 낱말을 그대로 쓴다. 한 줄 설명에만 쓰이는 표다
  const fixed = corpCode ? TAGLINE_OVERRIDE[corpCode] : undefined;
  if (fixed && fixed.length > 0) return fixed;
  const keywords = (focus?.direction?.keywords ?? []).filter((k) => !sameAsName(k, corpName));
  if (keywords.length > 0) return keywords.slice(0, 3);
  const segments = (profile?.segments ?? [])
    .filter((s) => s.revenueShare !== null && s.revenueShare > 0)
    .sort((a, b) => (b.revenueShare as number) - (a.revenueShare as number));
  if (segments.length > 0) return segments.slice(0, 2).map((s) => s.code);
  return (profile?.products ?? []).slice(0, 3);
}
