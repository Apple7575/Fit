import type { KeyMetricsData } from '../../types/metrics';
import { formatMetricCompact } from '../../utils/formatMetric';
import type { CompanyProfile } from '../company-profile/types';
import type { CompanyFocus } from '../focus-areas/types';

/**
 * 첫 화면의 한 줄. "TV · 가전 · 반도체로 333.6조 원을 버는 회사".
 * 무엇으로(키워드 → 사업부 → 제품 순으로 찾는다) + 얼마나(매출). 둘 다 없으면 null.
 * 판정 없이 데이터에 있는 말만 조합한다.
 */
export function buildTagline(
  profile: CompanyProfile | null,
  focus: CompanyFocus | null,
  metrics: KeyMetricsData | null,
): string | null {
  const what = pickWhat(profile, focus);
  const revenue = metrics?.metrics.find((m) => m.key === 'revenue')?.value ?? null;

  if (what.length > 0 && revenue !== null) {
    return `${what.join(' · ')}로 ${formatMetricCompact('KRW', revenue)} 원을 버는 회사`;
  }
  if (what.length > 0) return `${what.join(' · ')}를 하는 회사`;
  if (revenue !== null) return `한 해 매출 ${formatMetricCompact('KRW', revenue)} 원의 회사`;
  return null;
}

function pickWhat(profile: CompanyProfile | null, focus: CompanyFocus | null): string[] {
  const keywords = focus?.direction?.keywords ?? [];
  if (keywords.length > 0) return keywords.slice(0, 3);
  const segments = (profile?.segments ?? [])
    .filter((s) => s.revenueShare !== null && s.revenueShare > 0)
    .sort((a, b) => (b.revenueShare as number) - (a.revenueShare as number));
  if (segments.length > 0) return segments.slice(0, 2).map((s) => s.code);
  return (profile?.products ?? []).slice(0, 3);
}
