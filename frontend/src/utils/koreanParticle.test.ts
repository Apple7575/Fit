import { describe, expect, it } from 'vitest';
import { withInstrumental, withObject, withSubject } from './koreanParticle';

describe('withInstrumental', () => {
  it('받침이 없으면 로', () => {
    expect(withInstrumental('반도체')).toBe('반도체로');
    expect(withInstrumental('모빌리티')).toBe('모빌리티로');
  });

  it('받침이 있으면 으로', () => {
    // 실제로 "스마트폰로"·"금융업로"·"에어컨로" 가 화면에 나갔다
    expect(withInstrumental('스마트폰')).toBe('스마트폰으로');
    expect(withInstrumental('금융업')).toBe('금융업으로');
    expect(withInstrumental('에어컨')).toBe('에어컨으로');
  });

  it('ㄹ 받침만은 로', () => {
    expect(withInstrumental('건설')).toBe('건설로');
    expect(withInstrumental('세포주 개발')).toBe('세포주 개발로');
  });

  it('영문·숫자로 끝나면 받침이 없는 것으로 본다', () => {
    expect(withInstrumental('EV')).toBe('EV로');
    expect(withInstrumental('IT기기')).toBe('IT기기로');
    expect(withInstrumental('NAND Flash')).toBe('NAND Flash로');
  });
});

describe('withObject', () => {
  it('받침에 따라 을·를', () => {
    expect(withObject('반도체')).toBe('반도체를');
    expect(withObject('가전')).toBe('가전을');
  });
});

describe('withSubject', () => {
  it('받침에 따라 이·가', () => {
    expect(withSubject('수달')).toBe('수달이');
    expect(withSubject('여우')).toBe('여우가');
  });
});
