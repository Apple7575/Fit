import { CHARACTER_BY_KEY, characterForAgent } from '../../components/brand/characters';

export interface AgentPalette {
  /** 캐릭터 색 그대로. 점과 이름표 앞 표시에 쓴다 */
  hue: string;
  /** 글자에 쓰는 진한 쪽. 캐릭터 색 그대로 쓰면 병아리(노랑)나 여우(주황)가 흰 바탕에서 안 읽힌다 */
  ink: string;
  /** 말풍선 바탕. 캐릭터 색을 아주 옅게 깐다 */
  tint: string;
  /** 말풍선 테두리 */
  line: string;
}

/**
 * 에이전트별 말풍선 색.
 *
 * <p>캐릭터 색에서 전부 끌어낸다. 색 목록을 따로 두면 캐릭터를 바꿨을 때 칩과 말풍선이
 * 다른 색이 되고, 그러면 누가 한 말인지 눈으로 이어지지 않는다.
 */
export function agentPalette(agentKey: string | null | undefined): AgentPalette {
  const hue = CHARACTER_BY_KEY[characterForAgent(agentKey)].hex;
  return {
    hue,
    ink: `color-mix(in srgb, ${hue} 50%, #0f172a)`,
    tint: `color-mix(in srgb, ${hue} 8%, white)`,
    line: `color-mix(in srgb, ${hue} 35%, white)`,
  };
}
