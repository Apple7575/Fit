import { describe, expect, it } from 'vitest';
import { toActivities, toFocus, toWorkforce } from './api';

describe('toActivities', () => {
  it('drops unknown types, nulls missing fields and sorts newest first', () => {
    const items = toActivities({
      items: [
        { year: 2023, type: 'ma', field: '전장', purpose: '사업 인수', amount: 1 },
        { year: 2025, type: 'facility', field: '', purpose: null },
        { year: 2024, type: 'dividend', field: 'x', purpose: 'y', amount: 2 },
      ],
    });

    expect(items).toEqual([
      { year: 2025, type: 'facility', field: null, purpose: null, amount: null },
      { year: 2023, type: 'ma', field: '전장', purpose: '사업 인수', amount: 1 },
    ]);
  });

  it('survives a response without items', () => {
    expect(toActivities({ items: undefined as never })).toEqual([]);
  });
});

describe('toWorkforce', () => {
  it('normalizes missing numbers to null and missing segments to an empty list', () => {
    expect(toWorkforce({})).toEqual({
      year: null,
      employeeTotalChange: null,
      segments: [],
    });
    expect(
      toWorkforce({
        year: 2025,
        employeeTotalChange: 10,
        segments: [{ name: 'DS', employeeChange: 4 }],
      }).segments,
    ).toEqual([{ name: 'DS', revenue: null, revenueShare: null, employeeChange: 4 }]);
  });
});

describe('toFocus', () => {
  it('keeps direction and rnd when they carry data', () => {
    const focus = toFocus({
      year: 2025,
      direction: { newBusiness: ['AI 반도체'], keywords: [], strategyChange: null },
      rnd: { expense: 100, growthRate: null, revenueRatio: 9, fields: ['HBM'] },
    });

    expect(focus.direction).toEqual({
      newBusiness: ['AI 반도체'],
      keywords: [],
      strategyChange: null,
    });
    expect(focus.rnd).toEqual({
      expense: 100,
      growthRate: null,
      revenueRatio: 9,
      fields: ['HBM'],
    });
  });

  it('turns an empty direction or all-null rnd into null', () => {
    const focus = toFocus({
      direction: { newBusiness: [], keywords: null, strategyChange: '' },
      rnd: { expense: null, fields: [] },
    });

    expect(focus).toEqual({ year: null, direction: null, rnd: null });
  });
});
