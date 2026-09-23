import type { CharacterKey } from '../../components/brand/characters';
import type { KeyMetricsData } from '../../types/metrics';
import { formatChangeRate } from '../../utils/formatChangeRate';
import type { CompanyProfile } from '../company-profile/types';
import type { CompanyFocus } from '../focus-areas/types';

export interface FitPoint {
  key: 'business' | 'direction' | 'momentum' | 'rank';
  coach: CharacterKey;
  /** 사실 (데이터에서 온 한 문장) */
  fact: string;
  /** 지원자가 할 일 (한 줄) */
  action: string;
  /** 근거가 있는 상세 탭 */
  tab: 'business' | 'focus' | 'growth' | 'issues' | 'comparison';
}

export interface FitInputs {
  profile: CompanyProfile | null;
  focus: CompanyFocus | null;
  metrics: KeyMetricsData | null;
  /** 최근 뉴스 건수 (모르면 null) */
  newsCount: number | null;
  newsDays: number;
  /** 같은 업종 매출 순위 (모르면 null) */
  rank: number | null;
}

/**
 * "지원자라면 알아둘 것"을 데이터에서 규칙으로 뽑는다. 최대 3개, 값이 있는 것만.
 * 사실은 숫자 그대로, 행동은 그 사실을 자소서·면접에서 어떻게 쓰는지 한 줄.
 * 판정("좋은 회사")은 하지 않는다.
 */
export function buildFitPoints(input: FitInputs): FitPoint[] {
  const out: FitPoint[] = [];

  const shared = (input.profile?.segments ?? [])
    .filter((s) => s.revenueShare !== null && s.revenueShare > 0)
    .sort((a, b) => (b.revenueShare as number) - (a.revenueShare as number));
  if (shared.length > 0) {
    const top = shared[0];
    out.push({
      key: 'business',
      coach: 'otter',
      fact: `매출의 ${Math.round(top.revenueShare as number)}%가 ${top.code}에서 나와요`,
      action: '지원 직무가 이 부문과 어떻게 이어지는지 한 줄로 말할 수 있어야 해요.',
      tab: 'business',
    });
  }

  const keywords = input.focus?.direction?.keywords ?? [];
  const rnd = input.focus?.rnd;
  if (keywords.length > 0 || rnd?.revenueRatio != null) {
    const kw = keywords.slice(0, 3).join(' · ');
    const ratio = rnd?.revenueRatio != null ? `R&D에 매출의 ${rnd.revenueRatio.toFixed(1)}%` : '';
    out.push({
      key: 'direction',
      coach: 'owl',
      fact: kw && ratio ? `${kw}, 그리고 ${ratio}` : kw ? `집중하는 키워드는 ${kw}` : ratio,
      action: kw
        ? '지원동기에 이 키워드 중 하나로 관심을 증명하세요. 회사 말로 쓰면 눈에 띄어요.'
        : '연구·개발 비중이 큰 회사예요. 배우려는 태도보다 만들어 본 경험을 앞세우세요.',
      tab: 'focus',
    });
  }

  const rev = input.metrics?.metrics.find((m) => m.key === 'revenue')?.changeRate ?? null;
  const news = input.newsCount;
  if (rev !== null || (news !== null && news > 0)) {
    const parts: string[] = [];
    if (rev !== null) parts.push(`매출이 전년보다 ${formatChangeRate(rev)}`);
    if (news !== null && news > 0) parts.push(`최근 ${input.newsDays}일 뉴스 ${news}건`);
    out.push({
      key: 'momentum',
      coach: 'fox',
      fact: parts.join(', '),
      action:
        rev !== null && rev < 0
          ? '실적이 꺾인 해예요. "왜 지금 이 회사인지"를 스스로 답할 수 있어야 해요.'
          : '면접 전 최신 이슈 하나는 내 말로 설명할 수 있게 챙기세요.',
      tab: news !== null && news > 0 ? 'issues' : 'growth',
    });
  }

  if (out.length < 3 && input.rank !== null) {
    out.push({
      key: 'rank',
      coach: 'hamster',
      fact: `같은 업종에서 매출 ${input.rank}위예요`,
      action:
        input.rank <= 3
          ? '업계 상위권이면 "왜 이 회사"보다 "왜 나"가 더 많이 물어봐요.'
          : '상위 기업과 무엇이 다른지 한 가지는 알고 가세요.',
      tab: 'comparison',
    });
  }

  return out.slice(0, 3);
}
