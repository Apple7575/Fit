import { describe, expect, it } from 'vitest';
import { qwertyToHangul } from './qwertyToHangul';

describe('qwertyToHangul', () => {
  it('composes a syllable with a final consonant', () => {
    expect(qwertyToHangul('tka')).toBe('삼');
  });

  it('composes company names', () => {
    expect(qwertyToHangul('tkatjdwjswk')).toBe('삼성전자');
    expect(qwertyToHangul('zkzkdh')).toBe('카카오');
    expect(qwertyToHangul('guseo')).toBe('현대');
  });

  it('moves a final consonant to the next syllable when a vowel follows', () => {
    expect(qwertyToHangul('dkssud')).toBe('안녕');
  });

  it('composes paired vowels and paired final consonants', () => {
    expect(qwertyToHangul('ghk')).toBe('화');
    expect(qwertyToHangul('dkswk')).toBe('안자');
    expect(qwertyToHangul('dksg')).toBe('않');
  });

  it('keeps shifted keys as their tense jamo', () => {
    expect(qwertyToHangul('Rna')).toBe('꿈');
  });

  it('leaves digits and spaces where they are', () => {
    expect(qwertyToHangul('tka 3')).toBe('삼 3');
  });

  it('leaves a keyword that already has hangul alone', () => {
    expect(qwertyToHangul('삼성')).toBe('삼성');
    expect(qwertyToHangul('삼성 tka')).toBe('삼성 tka');
  });

  it('leaves a keyword without letters alone', () => {
    expect(qwertyToHangul('005930')).toBe('005930');
    expect(qwertyToHangul('')).toBe('');
  });

  it('keeps leftover jamo that cannot be composed', () => {
    expect(qwertyToHangul('rt')).toBe('ㄱㅅ');
    expect(qwertyToHangul('k')).toBe('ㅏ');
  });
});
