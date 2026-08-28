/**
 * 값이 있는데도 막대가 아예 안 보이면 "미제공" 과 구분되지 않는다.
 * 대기업과 중소기업의 매출 차이가 수백 배라 반올림하면 0% 가 되므로 최소 폭을 준다.
 */
const MIN_VISIBLE_PERCENT = 1.5;

/**
 * 가장 큰 값을 100% 로 두고 막대 길이를 비율로 환산한다.
 * 영업손실 같은 음수는 절댓값 기준으로 길이를 정하고, 방향은 색으로 구분한다.
 * 값이 없으면 0 을 돌려주어 막대를 그리지 않는다.
 */
export const barWidthPercent = (value: number | null, max: number): number => {
  if (value === null || value === 0 || max <= 0) {
    return 0;
  }

  const percent = Math.round((Math.abs(value) / max) * 1000) / 10;

  return Math.max(percent, MIN_VISIBLE_PERCENT);
};

/**
 * 막대 기준이 되는 최댓값. 음수도 막대를 그리므로 절댓값으로 비교한다.
 * 값이 하나도 없으면 0.
 */
export const maxPeerValue = (values: Array<number | null>): number =>
  values.reduce<number>(
    (max, value) => (value !== null && Math.abs(value) > max ? Math.abs(value) : max),
    0,
  );
