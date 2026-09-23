import {
  FRAMING_OK,
  FRONTAL_OK,
  GAZE_OK,
  HEAD_DOWN_WARN,
  MOVEMENT_WARN,
  ROLL_WARN,
  EXPRESSION_FLAT,
  type NonverbalMetrics,
} from './vision';

/** 0~1 비율을 % 로 */
const pct = (x: number) => Math.round(x * 100);

export interface Gauge {
  label: string;
  /** 0~100 */
  value: number;
  ok: boolean;
  /** 적정 기준 안내 */
  basis: string;
  hint: string;
}

/** 비율 지표를 "적정 기준 이상/미만"으로 바꾼다. 감정 판단은 하지 않고 관찰값만 쓴다. */
export function nonverbalGauges(m: NonverbalMetrics): Gauge[] {
  const out: Gauge[] = [];
  if (m.hasFace && m.faceRatio >= 0.4) {
    out.push({
      label: '화면 안에 얼굴',
      value: pct(m.inFrameRatio),
      ok: m.inFrameRatio >= FRAMING_OK,
      basis: `${pct(FRAMING_OK)}% 이상`,
      hint: '얼굴을 화면 가운데에 두세요',
    });
    out.push({
      label: '정면 유지',
      value: pct(m.frontalRatio),
      ok: m.frontalRatio >= FRONTAL_OK,
      basis: `${pct(FRONTAL_OK)}% 이상`,
      hint: '고개를 정면으로 향해 보세요',
    });
    out.push({
      label: '카메라 응시',
      value: pct(m.gazeRatio),
      ok: m.gazeRatio >= GAZE_OK,
      basis: `${pct(GAZE_OK)}% 이상`,
      hint: '렌즈를 보며 말해 보세요',
    });
    out.push({
      label: '고개 들기',
      value: pct(1 - (m.headDownRatio ?? 0)),
      ok: (m.headDownRatio ?? 0) <= HEAD_DOWN_WARN,
      basis: `${pct(1 - HEAD_DOWN_WARN)}% 이상`,
      hint: '말할 때 고개를 들고 정면을 보세요',
    });
    out.push({
      label: '머리 안정',
      value: pct(1 - m.headMovement),
      ok: m.headMovement <= MOVEMENT_WARN,
      basis: `${pct(1 - MOVEMENT_WARN)}% 이상`,
      hint: '고개 움직임을 줄여 보세요',
    });
  }
  /*
   * 상체·어깨·손짓은 여기서도 빼 둔다. 화면에서 감추면서 점수에는 세면, 사용자는 까닭을
   * 알 수 없는 "태도 3개 확인"을 보게 된다. 자세한 사정은 vision.describeNonverbal 에 적었다.
   */

  // 아래 셋은 새로 재는 값이다. 옛 기록에는 없으므로 플래그가 선 기록에서만 넣는다
  if (m.hasFace && m.headRollDeg > 0) {
    out.push({
      label: '고개 기울기',
      value: Math.max(0, 100 - Math.round((m.headRollDeg / ROLL_WARN) * 100)),
      ok: m.headRollDeg <= ROLL_WARN,
      basis: `기울기 ${ROLL_WARN}° 이하`,
      hint: `고개가 ${Math.round(m.headRollDeg)}° 기울어 있어요`,
    });
  }
  if (m.hasExpression) {
    out.push({
      label: '표정 변화',
      value: Math.min(100, Math.round((m.expressionRange / EXPRESSION_FLAT) * 100)),
      ok: m.expressionRange >= EXPRESSION_FLAT,
      basis: '내내 같은 표정이 아니면 적정',
      hint: '표정이 굳어 있으면 듣는 쪽도 긴장합니다',
    });
  }
  return out;
}
