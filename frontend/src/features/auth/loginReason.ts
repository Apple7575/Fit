import type { CharacterKey } from '../../components/brand/characters';

export interface LoginReason {
  /** 사진 위 큰 글씨 */
  headline: string;
  /** 폼 카드 부제. 왜 로그인이 필요한지 한 줄 */
  note: string;
  /** 말풍선 대사(순환) */
  lines: string[];
  character: CharacterKey;
}

/** 아무 데서도 튕겨 오지 않았을 때 (헤더의 로그인 버튼 등) */
const DEFAULT: LoginReason = {
  headline: '돌아오셨네요, 이어서 볼까요?',
  note: '자소서·면접 기록은 로그인한 나에게만 보입니다.',
  lines: ['어서 오세요, 기다렸어요', '지난번 보던 회사 이어서 볼까요?'],
  character: 'fox',
};

/**
 * 돌아갈 경로별 안내. 위에서부터 먼저 맞는 것을 쓴다.
 *
 * <p>무엇을 하려다 막혔는지 모른 채 "로그인" 한 장만 보면, 왜 계정이 필요한지 알 수 없어
 * 그냥 나간다. 특히 모의 면접은 "내 얼굴을 찍는데 왜 로그인까지"라는 생각이 들기 쉬우므로,
 * 계정이 필요한 까닭과 영상이 어디에 남는지를 같은 자리에서 밝힌다.
 */
const BY_PATH: Array<{ prefix: string } & LoginReason> = [
  {
    prefix: '/interviews',
    headline: '면접, 로그인하고 시작해요',
    note: '질문을 만들고 답변을 분석하려면 계정이 필요해요. 녹화한 영상은 이 브라우저에만 남습니다.',
    lines: ['면접 질문은 회사 자료로 만들어요', '녹화는 이 브라우저 밖으로 안 나가요'],
    character: 'owl',
  },
  {
    prefix: '/cover-letters',
    headline: '자소서, 로그인하면 저장돼요',
    note: '쓰던 자소서와 코치들의 검토 기록이 내 계정에 남습니다.',
    lines: ['문장은 짧게, 근거는 앞에!', '쓰다 만 것도 그대로 남아요'],
    character: 'chick',
  },
  {
    prefix: '/agent-rooms',
    headline: '검토 방, 로그인하고 열어요',
    note: '코치들이 자소서를 읽으려면 내 계정에 연결돼 있어야 해요.',
    lines: ['다들 의견 모아서 정리할게요'],
    character: 'lead',
  },
];

/** 로그인 화면이 어떤 말을 할지. redirect 경로에서 무엇을 하려다 막혔는지 읽는다. */
export function loginReason(redirect: string | null | undefined): LoginReason {
  if (!redirect || !redirect.startsWith('/')) return DEFAULT;
  const found = BY_PATH.find(
    ({ prefix }) => redirect === prefix || redirect.startsWith(`${prefix}/`) || redirect.startsWith(`${prefix}?`),
  );
  return found ?? DEFAULT;
}
