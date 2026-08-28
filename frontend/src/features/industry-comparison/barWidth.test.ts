import { describe, expect, it } from 'vitest';
import { barWidthPercent, maxPeerValue } from './barWidth';

describe('barWidthPercent', () => {
  it('gives the largest value a full bar', () => {
    expect(barWidthPercent(300, 300)).toBe(100);
  });

  it('scales smaller values against the largest', () => {
    expect(barWidthPercent(66, 300)).toBe(22);
  });

  it('keeps a tiny value visible instead of collapsing it to nothing', () => {
    // 0.1% 라 반올림하면 사라진다. 값이 있다는 사실 자체가 보여야 한다.
    expect(barWidthPercent(1, 1000)).toBe(1.5);
  });

  it('draws a negative value by its magnitude', () => {
    expect(barWidthPercent(-150, 300)).toBe(50);
  });

  it('draws nothing for a missing value', () => {
    expect(barWidthPercent(null, 300)).toBe(0);
  });

  it('draws nothing for exactly zero', () => {
    expect(barWidthPercent(0, 300)).toBe(0);
  });

  it('draws nothing when there is no positive maximum', () => {
    expect(barWidthPercent(10, 0)).toBe(0);
  });
});

describe('maxPeerValue', () => {
  it('returns the largest value, ignoring nulls', () => {
    expect(maxPeerValue([100, null, 300, 50])).toBe(300);
  });

  it('compares by magnitude so a large loss still sets the scale', () => {
    expect(maxPeerValue([100, -900])).toBe(900);
  });

  it('returns 0 when every value is missing', () => {
    expect(maxPeerValue([null, null])).toBe(0);
  });
});
