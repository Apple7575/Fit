import { describe, expect, it } from 'vitest';
import { hangulToRoman, romanToHangul } from './spelling';

describe('romanToHangul', () => {
  it('아는 이름으로 쳐도 공시명으로 바꿔 준다', () => {
    // 삼성SDS 의 DART 공시명은 "삼성에스디에스" 다. 아는 이름을 치면 한 건도 안 나왔다
    expect(romanToHangul('삼성SDS')).toBe('삼성에스디에스');
  });

  it('통째로 읽는 그룹 이름은 글자별로 쪼개지 않는다', () => {
    // 엘아이가 아니라 엘지다
    expect(romanToHangul('LG이노텍')).toBe('엘지이노텍');
    expect(romanToHangul('SK하이닉스')).toBe('에스케이하이닉스');
  });

  it('소문자로 쳐도 같다', () => {
    expect(romanToHangul('삼성sds')).toBe('삼성에스디에스');
  });

  it('영문이 없으면 그대로 돌려준다', () => {
    expect(romanToHangul('삼성전자')).toBe('삼성전자');
    expect(romanToHangul('')).toBe('');
  });
});

describe('hangulToRoman', () => {
  it('한글로 친 그룹 이름을 영문 공시명으로 바꾼다', () => {
    // "엘지" 로 찾으면 0건이었다 — 공시명이 "LG전자" 다
    expect(hangulToRoman('엘지')).toBe('LG');
    expect(hangulToRoman('엘지화학')).toBe('LG화학');
    expect(hangulToRoman('에스케이하이닉스')).toBe('SK하이닉스');
  });

  it('긴 이름을 먼저 맞춘다', () => {
    // "에스케이" 가 "에스"+"케이" 로 쪼개지면 엉뚱한 말이 된다
    expect(hangulToRoman('에스케이')).toBe('SK');
  });

  it('뒤쪽 글자는 건드리지 않는다', () => {
    // "이" 를 E 로 보면 "LGE노텍" 이 된다
    expect(hangulToRoman('엘지이노텍')).toBe('LG이노텍');
  });

  it('그룹 이름으로 시작하지 않으면 그대로 돌려준다', () => {
    expect(hangulToRoman('삼성전자')).toBe('삼성전자');
    // 가운데에 있는 것은 바꾸지 않는다 — 디에스케이는 그 자체가 회사 이름이다
    expect(hangulToRoman('디에스케이')).toBe('디에스케이');
  });
});
