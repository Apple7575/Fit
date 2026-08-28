import type { IndustryPeer, SortOrder } from './types';

/**
 * 지표 값 기준으로 정렬한다.
 * 값이 없는 기업(null)은 정렬 방향과 무관하게 항상 뒤로 보낸다.
 * 오름차순에서 "미제공"이 맨 앞에 오면 최솟값처럼 읽히기 때문이다.
 */
export const sortPeers = (
  peers: IndustryPeer[],
  order: SortOrder,
): IndustryPeer[] =>
  [...peers].sort((a, b) => {
    if (a.value === null && b.value === null) {
      return 0;
    }
    if (a.value === null) {
      return 1;
    }
    if (b.value === null) {
      return -1;
    }

    return order === 'desc' ? b.value - a.value : a.value - b.value;
  });
