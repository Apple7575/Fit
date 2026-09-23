import { describe, expect, it } from 'vitest';
import type { KeyMetricsData } from '../../types/metrics';
import type { CompanyProfile } from '../company-profile/types';
import type { CompanyFocus } from '../focus-areas/types';
import { buildTagline } from './tagline';

const focusWith = (keywords: string[]) => ({ direction: { keywords } }) as unknown as CompanyFocus;
const profileWith = (partial: Partial<CompanyProfile>) => partial as CompanyProfile;
const revenue = (value: number) =>
  ({ metrics: [{ key: 'revenue', value }] }) as unknown as KeyMetricsData;

describe('buildTagline', () => {
  it('앞 낱말의 받침을 보고 조사를 고른다', () => {
    // 붙박이로 "로"를 쓰던 때에는 "스마트폰로 333.6조 원" 이 나갔다
    const line = buildTagline(null, focusWith(['TV', '가전', '스마트폰']), revenue(333_600_000_000_000));
    expect(line).toContain('스마트폰으로');
    expect(line).not.toContain('스마트폰로');
  });

  it('받침이 없으면 로를 쓴다', () => {
    expect(buildTagline(null, focusWith(['메모리 반도체']), revenue(1_000))).toContain('메모리 반도체로');
  });

  it('매출이 없으면 을·를로 맺는다', () => {
    expect(buildTagline(null, focusWith(['철강', '무역', '건설']), null)).toBe('철강 · 무역 · 건설을 하는 회사');
  });

  it('회사 이름을 그대로 되풀이하는 키워드는 뺀다', () => {
    const line = buildTagline(null, focusWith(['카카오', '커머스', '모빌리티', '게임']), null, '카카오');
    expect(line).toBe('커머스 · 모빌리티 · 게임을 하는 회사');
  });

  it('이름을 품고 있을 뿐인 제품은 남긴다', () => {
    // "들어 있으면 뺀다"로 하면 카카오의 가장 좋은 키워드가 사라진다
    const line = buildTagline(null, focusWith(['카카오톡', '커머스', '모빌리티']), null, '카카오');
    expect(line).toBe('카카오톡 · 커머스 · 모빌리티를 하는 회사');
  });

  it('이름을 뺀 키워드가 하나도 없으면 사업부로 내려간다', () => {
    const line = buildTagline(
      profileWith({ segments: [{ code: '반도체 부문', revenueShare: 100 }] as CompanyProfile['segments'] }),
      focusWith(['SK하이닉스']),
      null,
      'SK하이닉스',
    );
    expect(line).toBe('반도체 부문을 하는 회사');
  });

  it('무엇도 매출도 없으면 만들지 않는다', () => {
    expect(buildTagline(null, null, null)).toBeNull();
  });
});
