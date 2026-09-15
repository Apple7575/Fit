/**
 * 코치 캐릭터 5명. 검토 방 에이전트(features/agent-room/agentStyle.ts)와 1:1 로 대응한다.
 * `image` 가 비어 있으면 CharacterSlot 이 자리 표시 캐릭터를 그린다. 실제 그림이 오면
 * public/characters/<key>-<pose>.png 로 넣고 여기 image 만 채우면 된다.
 */
export type CharacterKey = 'fox' | 'chick' | 'hamster' | 'otter' | 'owl';

export type CharacterPose = 'hello' | 'search' | 'mail' | 'empty' | 'talk';

export interface Character {
  key: CharacterKey;
  name: string;
  /** 검토 방 에이전트 역할 */
  role: string;
  agentKey: 'news' | 'writing' | 'jd' | 'company' | 'position';
  /** Tailwind 색 클래스 접미사 (bg-fox, text-fox, bg-fox-soft …) */
  color: CharacterKey;
  hex: string;
  /** 랜딩 말풍선·마퀴에 쓰는 대사 */
  lines: string[];
  /** 무엇을 봐 주는지 (뒤집힌 카드) */
  checks: string[];
  /** 포즈별 이미지 경로. 없으면 자리 표시 */
  image?: Partial<Record<CharacterPose, string>>;
}

export const CHARACTERS: Character[] = [
  {
    key: 'fox',
    name: '여우',
    role: '뉴스·트렌드 담당',
    agentKey: 'news',
    color: 'fox',
    hex: '#f97316',
    lines: ['요즘 이 회사 뉴스는 제가 다 봤어요', '최근 30일 이슈부터 볼까요?'],
    checks: ['최근 30일 뉴스와 이슈 분류', '투자·기술 이슈 흐름', '자소서에 넣을 만한 최신 근거'],
  },
  {
    key: 'otter',
    name: '수달',
    role: '기업 담당',
    agentKey: 'company',
    color: 'otter',
    hex: '#14b8a6',
    lines: ['사업보고서 300쪽은 제가 읽었어요', '이 회사가 힘 싣는 분야, 알려드릴게요'],
    checks: ['사업보고서 기반 사업 방향', 'R&D·투자·인력 변화', '동종 업계 안에서의 위치'],
  },
  {
    key: 'hamster',
    name: '햄스터',
    role: '채용공고 담당',
    agentKey: 'jd',
    color: 'hamster',
    hex: '#b45309',
    lines: ['공고에 XML 경험이 있네요, 앞세우죠', '자격요건과 우대사항을 나눠 볼게요'],
    checks: ['채용공고의 자격·우대 요건', '공고 문장과 답변의 대응', '빠진 키워드'],
  },
  {
    key: 'owl',
    name: '부엉이',
    role: '포지션 담당',
    agentKey: 'position',
    color: 'owl',
    hex: '#8b5cf6',
    lines: ['이 직무는 이런 관점을 봅니다', '백엔드라면 장애 경험을 물어볼 거예요'],
    checks: ['직무별로 면접관이 보는 관점', '경험을 직무 언어로 바꾸기', '예상 질문'],
  },
  {
    key: 'chick',
    name: '병아리',
    role: '글쓰기 담당',
    agentKey: 'writing',
    color: 'chick',
    hex: '#facc15',
    lines: ['문장은 짧게, 근거는 앞에!', '지원동기로 연결하죠'],
    checks: ['문장 길이와 논리 순서', '구체성·가독성·맞춤법', '글자 수 안에서 다듬기'],
  },
];

export const CHARACTER_BY_KEY = Object.fromEntries(
  CHARACTERS.map((character) => [character.key, character]),
) as Record<CharacterKey, Character>;
