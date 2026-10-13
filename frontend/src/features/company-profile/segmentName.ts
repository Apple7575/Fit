import type { ProfileSegment } from './types';

/**
 * 사업부 이름에서 꾸밈말을 걷어낸다. "DS 부문" · "석유화학사업부문" → "DS" · "석유화학".
 *
 * <p>"부문"·"사업"은 이름 끝이 아니라 가운데에도 온다("공통부문 및 기타" ↔ "공통 및 기타부문").
 * 그래서 끝만 자르지 않고 어디에 있든 걷어낸 뒤 견준다.
 */
export function normalizeSegment(code: string): string {
  return code
    .replace(/사업부문|사업부|사업|부문/g, '')
    .replace(/\s+/g, '')
    .toUpperCase();
}

/**
 * 매출을 공시하지 않은 사업부 가운데, 공시된 사업부와 같은 것을 걷어낸다.
 *
 * <p>같은 사업부가 이름만 달리 두 번 오는 기록이 있다. 삼성전자는 "DX 부문 56.3%"·"DS 부문
 * 39%" 를 공시해 놓고 "DX"·"DS" 가 따로 또 들어와, 도넛 아래에 "DS 미공시"·"DX 미공시" 두
 * 줄이 붙었다. 위에서 수치를 다 보여 준 부문을 아래에서 "안 알려 준다"고 말하는 셈이다.
 *
 * <p>이름이 정말 다른 것(현대자동차의 "자동차부문", NAVER 의 "전사")은 그대로 남긴다.
 * 진짜로 매출을 공시하지 않은 부문이라 알려 주는 편이 맞다.
 */
export function realUndisclosed(segments: ProfileSegment[]): ProfileSegment[] {
  const disclosed = new Set(
    segments.filter((s) => s.revenue !== null).map((s) => normalizeSegment(s.code)),
  );
  return segments.filter((s) => s.revenue === null && !disclosed.has(normalizeSegment(s.code)));
}
