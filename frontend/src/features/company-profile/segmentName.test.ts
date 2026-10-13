import { describe, expect, it } from 'vitest';
import { normalizeSegment, realUndisclosed } from './segmentName';
import type { ProfileSegment } from './types';

const has = (code: string): ProfileSegment => ({ code, revenue: 1_000, revenueShare: 10 });
const none = (code: string): ProfileSegment => ({ code, revenue: null, revenueShare: null });
const codes = (list: ProfileSegment[]) => list.map((s) => s.code);

describe('normalizeSegment', () => {
  it('꾸밈말을 걷어낸다', () => {
    expect(normalizeSegment('DS 부문')).toBe('DS');
    expect(normalizeSegment('반도체 부문')).toBe('반도체');
    expect(normalizeSegment('석유화학사업부문')).toBe('석유화학');
  });

  it('가운데에 낀 꾸밈말도 걷어낸다', () => {
    // "공통부문 및 기타" 와 "공통 및 기타부문" 은 같은 부문인데 어순이 다르다
    expect(normalizeSegment('공통부문 및 기타')).toBe(normalizeSegment('공통 및 기타부문'));
  });
});

describe('realUndisclosed', () => {
  it('삼성전자: 수치를 보여 준 부문이 미공시로 또 나오지 않는다', () => {
    const segments = [
      has('DX 부문'),
      has('DS 부문'),
      has('SDC'),
      has('Harman'),
      has('기타'),
      none('DS'),
      none('DX'),
    ];
    expect(realUndisclosed(segments)).toEqual([]);
  });

  it('SK하이닉스: "반도체" 와 "반도체 부문" 을 같은 것으로 본다', () => {
    expect(realUndisclosed([has('반도체 부문'), none('반도체')])).toEqual([]);
  });

  it('LG화학: 사업부문 접미사만 다른 것들을 걷어낸다', () => {
    const segments = [
      has('석유화학사업부문'),
      has('첨단소재사업부문'),
      has('생명과학사업부문'),
      has('공통 및 기타부문'),
      none('석유화학'),
      none('첨단소재'),
      none('생명과학'),
      none('공통부문 및 기타'),
    ];
    expect(realUndisclosed(segments)).toEqual([]);
  });

  it('이름이 정말 다르면 미공시로 남긴다', () => {
    // 현대자동차는 "제품" 만 공시하고 "자동차부문" 은 수치가 없다 — 알려 주는 편이 맞다
    expect(codes(realUndisclosed([has('제품'), none('자동차부문')]))).toEqual(['자동차부문']);
    expect(codes(realUndisclosed([has('서치플랫폼'), none('전사')]))).toEqual(['전사']);
  });

  it('비슷해 보여도 다른 이름은 묶지 않는다', () => {
    expect(codes(realUndisclosed([has('전자'), none('전자재료')]))).toEqual(['전자재료']);
  });

  it('공시된 것이 하나도 없으면 전부 남긴다', () => {
    const segments = [none('항공운송사업'), none('항공우주사업'), none('기타')];
    expect(codes(realUndisclosed(segments))).toEqual(['항공운송사업', '항공우주사업', '기타']);
  });
});
