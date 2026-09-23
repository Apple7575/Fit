import { describe, expect, it } from 'vitest';
import type { MetricRow, Tone } from './delivery';
import { IMPACT, orderMetrics, warnCount } from './metricFocus';

const row = (key: string, tone: Tone = 'warn'): MetricRow => ({ key, value: '-', tone });
const keys = (rows: MetricRow[]) => rows.map((r) => r.key);

describe('orderMetrics', () => {
  it('살펴볼 것이 앞, 적정이 가운데, 재지 못한 것이 맨 뒤', () => {
    const sorted = orderMetrics([row('표정', 'none'), row('말 속도', 'good'), row('어깨 수평', 'warn')]);
    expect(keys(sorted)).toEqual(['어깨 수평', '말 속도', '표정']);
  });

  it('같은 상태끼리는 면접관이 먼저 알아차리는 순서', () => {
    const sorted = orderMetrics([row('어깨 수평'), row('카메라 응시'), row('말 속도')]);
    expect(keys(sorted)).toEqual(['카메라 응시', '말 속도', '어깨 수평']);
  });

  it('모르는 지표는 맨 뒤로 보내되 빠뜨리지 않는다', () => {
    const sorted = orderMetrics([row('새로 생긴 지표'), row('말 속도')]);
    expect(keys(sorted)).toEqual(['말 속도', '새로 생긴 지표']);
  });

  it('한 장도 버리지 않는다', () => {
    const rows = [row('표정', 'none'), row('말 속도', 'good'), row('어깨 수평')];
    expect(orderMetrics(rows)).toHaveLength(rows.length);
  });

  it('넘겨받은 배열을 건드리지 않는다', () => {
    const rows = [row('어깨 수평', 'good'), row('카메라 응시')];
    orderMetrics(rows);
    expect(keys(rows)).toEqual(['어깨 수평', '카메라 응시']);
  });
});

describe('warnCount', () => {
  it('재지 못한 항목은 세지 않는다', () => {
    // 마이크가 꺼져 있던 건 사용자가 잘못한 게 아니다
    expect(warnCount([row('얼굴 인식', 'none'), row('표정', 'none'), row('말 속도', 'good')])).toBe(0);
  });

  it('어긋난 것만 센다', () => {
    expect(warnCount([row('말 속도'), row('표정'), row('어깨 수평', 'good')])).toBe(2);
  });
});

describe('IMPACT', () => {
  it('화면에 나오는 지표에는 "왜 중요한지"가 다 있다', () => {
    const shown = [
      '말 속도',
      '습관어(음·어)',
      '답변 길이',
      '말이 멈춘 시간',
      '목소리 크기',
      '얼굴 위치',
      '정면 유지',
      '카메라 응시',
      '고개 흔들림',
      '고개 각도',
      '고개 기울기',
      '상체 자세',
      '상체 안정',
      '어깨 수평',
      '표정',
      '손짓',
      '얼굴 인식',
    ];
    expect(shown.filter((key) => !IMPACT[key])).toEqual([]);
  });
});
