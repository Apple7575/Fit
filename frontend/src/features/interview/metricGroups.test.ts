import { describe, expect, it } from 'vitest';
import type { MetricRow } from './delivery';
import { groupMetrics, groupStatus } from './metricGroups';

const row = (key: string, tone: MetricRow['tone'] = 'good'): MetricRow => ({ key, value: '값', tone });

describe('groupMetrics', () => {
  it('지표를 말하기·목소리·시선·자세 네 묶음으로 나눈다', () => {
    const groups = groupMetrics([
      row('말 속도'),
      row('답변 길이'),
      row('말이 멈춘 시간'),
      row('얼굴 위치'),
      row('상체 자세'),
    ]);

    expect(groups.map((g) => g.title)).toEqual(['말하기', '목소리', '시선과 표정', '자세']);
    expect(groups[0].rows.map((r) => r.key)).toEqual(['말 속도', '답변 길이']);
  });

  it('값이 없는 묶음은 만들지 않는다', () => {
    const groups = groupMetrics([row('말 속도')]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('speech');
  });

  it('정의에 없는 지표는 그 밖으로 모은다', () => {
    const groups = groupMetrics([row('새로 생긴 지표')]);
    expect(groups.map((g) => g.title)).toEqual(['그 밖']);
  });

  it('고칠 것 개수를 세고, 상태 줄에 그 이름을 쓴다', () => {
    const [speech] = groupMetrics([row('말 속도', 'warn'), row('답변 길이'), row('습관어(음·어)', 'warn')]);
    expect(speech.warnCount).toBe(2);
    expect(groupStatus(speech)).toBe('말 속도 · 습관어(음·어)');
  });

  it('모두 적정이면 개수로 알린다', () => {
    const [speech] = groupMetrics([row('말 속도'), row('답변 길이')]);
    expect(groupStatus(speech)).toBe('2개 항목 모두 적정');
  });
});
