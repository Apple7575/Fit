import { describe, expect, it } from 'vitest';
import { nonverbalGauges } from './nonverbalGauges';
import { describeNonverbal, type NonverbalMetrics } from './vision';

/** 무엇이든 최악으로 잡힌 기록. 이래도 상체·어깨·손짓은 말하지 않는다. */
const worst: NonverbalMetrics = {
  faceRatio: 1,
  inFrameRatio: 1,
  frontalRatio: 1,
  gazeRatio: 1,
  headMovement: 0,
  postureStable: 0, // 상체가 계속 흔들림
  postureTiltDeg: 30, // 어깨가 크게 기울어짐
  headDownRatio: 0,
  slouchRatio: 1, // 내내 구부정
  headRollDeg: 2,
  smileRatio: 0.3,
  expressionRange: 1,
  handsVisibleRatio: 1,
  gestureAmount: 1, // 손이 계속 움직임
  hasFace: true,
  hasPose: true,
  hasExpression: true,
  hasHands: true,
};

/**
 * 어깨·손목 좌표(PoseLandmarker)로 재는 값은 노트북 구도에서 믿을 수 없어 리포트에서 뺐다.
 * 화면에서만 지우고 점수에는 남겨 두면 까닭을 알 수 없는 "태도 3개 확인"이 되므로 둘 다 본다.
 */
const HIDDEN = ['상체 자세', '상체 안정', '어깨 수평', '손짓'];

describe('describeNonverbal', () => {
  it('상체·어깨·손짓은 값이 아무리 나빠도 내놓지 않는다', () => {
    const keys = describeNonverbal(worst).map((r) => r.key);
    expect(keys.filter((k) => HIDDEN.includes(k))).toEqual([]);
  });

  it('얼굴로 재는 것은 그대로 말한다', () => {
    const keys = describeNonverbal(worst).map((r) => r.key);
    expect(keys).toContain('카메라 응시');
    expect(keys).toContain('고개 각도');
    expect(keys).toContain('표정');
  });

  it('상체만 잡히고 얼굴이 없으면 인식 실패만 알린다', () => {
    const noFace = { ...worst, hasFace: false, faceRatio: 0, hasExpression: false };
    const keys = describeNonverbal(noFace).map((r) => r.key);
    expect(keys.filter((k) => HIDDEN.includes(k))).toEqual([]);
    expect(keys).toContain('얼굴 인식');
  });
});

describe('nonverbalGauges', () => {
  it('점수에도 상체·어깨·손짓을 세지 않는다', () => {
    const labels = nonverbalGauges(worst).map((g) => g.label);
    expect(labels.filter((l) => ['바른 상체', '자세 안정', '어깨 수평', '손짓'].includes(l))).toEqual([]);
  });

  it('상체가 최악이어도 얼굴이 좋으면 모두 적정이다', () => {
    // 빼기 전에는 이 기록이 "태도 3개 확인"으로 나왔다
    expect(nonverbalGauges(worst).every((g) => g.ok)).toBe(true);
  });
});
