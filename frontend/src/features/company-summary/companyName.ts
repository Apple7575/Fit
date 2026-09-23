/**
 * 공시명과 사람들이 부르는 이름이 다른 곳.
 *
 * <p>DART 공시명이 한글 음차인데 정작 아무도 그렇게 부르지 않는 경우가 있다. "삼성SDS" 를
 * "삼성에스디에스" 라고 치는 사람은 없고, KT 도 마찬가지다. 그런데 화면에는 공시명이 뜨니
 * 검색으로 찾아 놓고도 "이게 내가 찾던 그 회사가 맞나" 싶어진다.
 *
 * <p>많지 않다. 전체 2,500여 곳 중 실제로 헷갈리는 것은 열 곳 남짓이고, 나머지는 스팩이거나
 * 애초에 달리 부르는 이름이 없다. 그래서 규칙으로 만들지 않고 확인한 것만 손으로 적는다 —
 * 한 글자씩 되돌리는 규칙은 멀쩡한 이름을 망가뜨린다("엘지이노텍" → "LGE노텍").
 *
 * <p>넣는 기준: 그 이름으로 부르는 것이 확실할 때만. 애매하면 넣지 않는다. 틀린 이름을
 * 보여 주는 것은 공시명을 그대로 두는 것보다 나쁘다.
 */
const ALIAS: Record<string, string> = {
  삼성에스디에스: '삼성SDS',
  케이티: 'KT',
  케이티스카이라이프: 'KT스카이라이프',
  케이티알파: 'KT알파',
  케이티앤지: 'KT&G',
  에스케이바이오팜: 'SK바이오팜',
  엘에스일렉트릭: 'LS일렉트릭',
  에스디바이오센서: 'SD바이오센서',
  한국전력공사: '한국전력',
};

/**
 * 화면에 보여 줄 이름. 부르는 이름이 있으면 그것으로, 없으면 공시명 그대로.
 *
 * <p>둘을 나란히 적어 보기도 했는데("삼성에스디에스 삼성SDS") 읽을 것만 늘었다. 아무도
 * 쓰지 않는 이름을 굳이 앞세울 이유가 없다 — 검색은 두 철자를 모두 받아 주므로 공시명으로
 * 찾는 사람도 그대로 찾는다.
 */
export function displayName(corpName: string): string {
  return ALIAS[corpName.trim()] ?? corpName;
}

/** 부르는 이름 → 공시명. 이 말로 찾으면 공시명으로도 한 번 더 찾는다 */
const BY_ALIAS = new Map(
  Object.entries(ALIAS).map(([corpName, alias]) => [alias.toLowerCase(), corpName]),
);

/** 부르는 이름으로 친 경우 공시명을 돌려준다 ("KT&G" → "케이티앤지"). 없으면 null */
export function corpNameOfAlias(keyword: string): string | null {
  return BY_ALIAS.get(keyword.trim().toLowerCase()) ?? null;
}
