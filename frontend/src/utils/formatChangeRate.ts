/** 전년 대비 증감률(%)을 소수점 1자리·부호 명시로 표기한다 (+1.7%, -12.0%, 0.0%) */
export const formatChangeRate = (rate: number): string =>
  `${rate > 0 ? '+' : ''}${rate.toFixed(1)}%`;
