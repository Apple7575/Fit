import { describe, expect, it } from 'vitest';
import { formatMetricValue, formatMetricWithUnit, metricUnitLabel } from './formatMetric';

describe('formatMetric', () => {
  it('formats won metrics in 조/억', () => {
    expect(formatMetricWithUnit('revenue', 300_870_903_000_000)).toBe('300조 8,709억 원');
    expect(formatMetricWithUnit('averageSalary', 130_000_000)).toBe('1억 원');
  });

  it('formats head counts with thousands separators and 명', () => {
    expect(formatMetricWithUnit('employeeCount', 124_804)).toBe('124,804 명');
    expect(formatMetricValue('employeeCount', 124_804.4)).toBe('124,804');
  });

  it('formats tenure in years with one decimal, dropping .0', () => {
    expect(formatMetricWithUnit('averageTenure', 12.4)).toBe('12.4 년');
    expect(formatMetricWithUnit('averageTenure', 12)).toBe('12 년');
  });

  it('formats ratios as percent values as given', () => {
    expect(formatMetricWithUnit('rndToRevenueRatio', 8.3)).toBe('8.3 %');
    expect(formatMetricWithUnit('rndToRevenueRatio', 10)).toBe('10 %');
  });

  it('exposes the unit label per metric', () => {
    expect(metricUnitLabel('revenue')).toBe('원');
    expect(metricUnitLabel('employeeCount')).toBe('명');
    expect(metricUnitLabel('averageTenure')).toBe('년');
    expect(metricUnitLabel('rndToRevenueRatio')).toBe('%');
  });
});
