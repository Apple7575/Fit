/**
 * 코치 캐릭터. 검토 방 에이전트(features/agent-room)와 1:1 로 대응한다.
 * 그림 파일 없이 색 덩어리 + 눈·입·볼로 그리는 "돌멩이"가 정식 캐릭터다 (CharacterSlot).
 */
export type CharacterKey = 'fox' | 'chick' | 'hamster' | 'otter' | 'owl' | 'lead';

export type CharacterPose = 'hello' | 'search' | 'mail' | 'empty' | 'talk';

/** 코치별 얼굴 생김새. 색이 같아도 표정으로 구분된다. */
export type CharacterFace = 'sly' | 'calm' | 'puff' | 'wide' | 'rosy' | 'lead';

export interface Character {
  key: CharacterKey;
  name: string;
  /** 검토 방 에이전트 역할 */
  role: string;
  agentKey: 'news' | 'writing' | 'jd' | 'company' | 'position' | 'supervisor';
  /** 돌멩이 몸 색. 코치 다섯은 핑크·노랑·파랑·초록·보라 파스텔, 반장만 중립색 */
  hex: string;
  face: CharacterFace;
  /** 랜딩 말풍선·마퀴에 쓰는 대사 */
  lines: string[];
  /** 무엇을 봐 주는지 (뒤집힌 카드) */
  checks: string[];
}

/** 랜딩에 소개하는 코치 다섯. 총괄(반장)은 검토 방에서만 나온다. */
export const COACHES: Character[] = [
  {
    key: 'fox',
    name: '여우',
    role: '뉴스·트렌드 담당',
    agentKey: 'news',
    hex: '#f9a8d4',
    face: 'sly',
    lines: ['요즘 이 회사 뉴스는 제가 다 봤어요', '최근 30일 이슈부터 볼까요?'],
    checks: ['최근 30일 뉴스와 이슈 분류', '투자·기술 이슈 흐름', '자소서에 넣을 만한 최신 근거'],
  },
  {
    key: 'otter',
    name: '수달',
    role: '기업 담당',
    agentKey: 'company',
    hex: '#93c5fd',
    face: 'calm',
    lines: ['사업보고서 300쪽은 제가 읽었어요', '이 회사가 힘 싣는 분야, 알려드릴게요'],
    checks: ['사업보고서 기반 사업 방향', 'R&D·투자·인력 변화', '동종 업계 안에서의 위치'],
  },
  {
    key: 'hamster',
    name: '햄스터',
    role: '채용공고 담당',
    agentKey: 'jd',
    hex: '#86efac',
    face: 'puff',
    lines: ['공고에 XML 경험이 있네요, 앞세우죠', '자격요건과 우대사항을 나눠 볼게요'],
    checks: ['채용공고의 자격·우대 요건', '공고 문장과 답변의 대응', '빠진 키워드'],
  },
  {
    key: 'owl',
    name: '부엉이',
    role: '포지션 담당',
    agentKey: 'position',
    hex: '#c4b5fd',
    face: 'wide',
    lines: ['이 직무는 이런 관점을 봅니다', '백엔드라면 장애 경험을 물어볼 거예요'],
    checks: ['직무별로 면접관이 보는 관점', '경험을 직무 언어로 바꾸기', '예상 질문'],
  },
  {
    key: 'chick',
    name: '병아리',
    role: '글쓰기 담당',
    agentKey: 'writing',
    hex: '#fde047',
    face: 'rosy',
    lines: ['문장은 짧게, 근거는 앞에!', '지원동기로 연결하죠'],
    checks: ['문장 길이와 논리 순서', '구체성·가독성·맞춤법', '글자 수 안에서 다듬기'],
  },
];

const LEAD: Character = {
  key: 'lead',
  name: '반장',
  role: '총괄',
  agentKey: 'supervisor',
  hex: '#94a3b8',
  face: 'lead',
  lines: ['다들 의견 모아서 정리할게요'],
  checks: ['코치들 답변을 모아 근거 순서로 정리'],
};

export const CHARACTERS: Character[] = [...COACHES, LEAD];

export const CHARACTER_BY_KEY = Object.fromEntries(
  CHARACTERS.map((character) => [character.key, character]),
) as Record<CharacterKey, Character>;

const BY_AGENT = Object.fromEntries(
  CHARACTERS.map((character) => [character.agentKey, character.key]),
) as Record<Character['agentKey'], CharacterKey>;

/** 검토 방 agentKey(jd·company·position·news·writing·supervisor) → 캐릭터. 모르면 반장 */
export function characterForAgent(agentKey: string | null | undefined): CharacterKey {
  return (agentKey && BY_AGENT[agentKey as Character['agentKey']]) || 'lead';
}

/** 검토 방 제목("채용공고 담당" 등)으로 캐릭터를 되찾는다. 방 이름이 곧 에이전트 이름이다 */
export function characterForRoomTitle(title: string): CharacterKey {
  if (title.includes('채용공고')) return 'hamster';
  if (title.includes('기업')) return 'otter';
  if (title.includes('포지션')) return 'owl';
  if (title.includes('뉴스')) return 'fox';
  if (title.includes('글쓰기')) return 'chick';
  return 'lead';
}
