import { describe, expect, it } from 'vitest';
import { formatAmount } from './formatAmount';

describe('formatAmount', () => {
  it('formats trillions and hundred-millions of won', () => {
    expect(formatAmount(300_870_903_000_000)).toBe('300조 8,709억');
  });

  it('formats amounts below one trillion in 억 only', () => {
    expect(formatAmount(6_566_976_000_000)).toBe('6조 5,670억');
    expect(formatAmount(123_400_000_000)).toBe('1,234억');
  });

  it('formats amounts below one 억 in 만원', () => {
    expect(formatAmount(56_780_000)).toBe('5,678만');
  });

  it('keeps the sign for negative amounts', () => {
    expect(formatAmount(-2_500_000_000_000)).toBe('-2조 5,000억');
  });

  it('returns 0 for zero', () => {
    expect(formatAmount(0)).toBe('0');
  });
});
