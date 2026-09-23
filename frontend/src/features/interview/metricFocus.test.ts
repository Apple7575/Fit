import { describe, expect, it } from 'vitest';
import type { MetricRow, Tone } from './delivery';
import { IMPACT, pickFocus } from './metricFocus';

const row = (key: string, tone: Tone = 'warn'): MetricRow => ({ key, value: '-', tone });

describe('pickFocus', () => {
  it('어긋난 것만 고른다', () => {
    const focus = pickFocus([row('말 속도'), row('답변 길이', 'good'), row('표정', 'none')]);
    expect(focus.fixes.map((r) => r.key)).toEqual(['말 속도']);
    expect(focus.okCount).toBe(1);
    expect(focus.noneCount).toBe(1);
  });

  it('세 개까지만 펴 놓고 나머지는 세어 둔다', () => {
    const focus = pickFocus([row('어깨 수평'), row('손짓'), row('표정'), row('말 속도'), row('카메라 응시')]);
    expect(focus.fixes).toHaveLength(3);
    expect(focus.restCount).toBe(2);
  });

  it('면접관이 먼저 알아차리는 것을 앞에 둔다', () => {
    const focus = pickFocus([row('어깨 수평'), row('카메라 응시'), row('말 속도')]);
    expect(focus.fixes.map((r) => r.key)).toEqual(['카메라 응시', '말 속도', '어깨 수평']);
  });

  it('모르는 지표는 맨 뒤로 보내되 빠뜨리지 않는다', () => {
    const focus = pickFocus([row('새로 생긴 지표'), row('말 속도')]);
    expect(focus.fixes.map((r) => r.key)).toEqual(['말 속도', '새로 생긴 지표']);
  });

  it('재지 못한 항목은 고칠 것으로 세지 않는다', () => {
    // 마이크가 꺼져 있던 건 사용자가 잘못한 게 아니다
    const focus = pickFocus([row('얼굴 인식', 'none'), row('표정', 'none')]);
    expect(focus.fixes).toHaveLength(0);
    expect(focus.restCount).toBe(0);
  });
});

describe('IMPACT', () => {
  it('화면에 나오는 지표에는 "왜 문제인지"가 다 있다', () => {
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
