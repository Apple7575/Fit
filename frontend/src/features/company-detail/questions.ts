import type { CharacterKey } from '../../components/brand/characters';

/** 상세 페이지의 라우트 세그먼트. overview 는 요약, 나머지 다섯은 질문 하나씩 답하는 상세 탭이다 */
export type CompanyTab = 'overview' | CompanyQuestion['tab'];

export interface CompanyQuestion {
  tab: 'business' | 'growth' | 'focus' | 'comparison' | 'issues';
  /** 탭 라벨 (짧게) */
  short: string;
  /** 질문 형태의 제목. 요약 카드와 상세 탭 머리에 같이 쓴다 */
  title: string;
  /** 그 탭이 무엇으로 답하는지 */
  body: string;
  /** 이 질문을 맡은 코치. 다섯 질문이 서로 다른 코치를 하나씩 맡는다 */
  coach: CharacterKey;
}

/**
 * 회사 하나에 던지는 다섯 질문. 요약 화면은 질문마다 카드 한 장으로 답하고,
 * 카드를 누르면 같은 질문의 상세 탭으로 간다. 순서가 곧 탭 순서·카드 순서다.
 */
export const COMPANY_QUESTIONS: readonly CompanyQuestion[] = [
  {
    tab: 'business',
    short: '사업',
    title: '어떤 회사인가',
    body: '사업 소개 · 사업부 매출 구성 · 주요 제품',
    coach: 'otter',
  },
  {
    tab: 'growth',
    short: '성장',
    title: '얼마나 컸나',
    body: '5년 매출·이익·인력 추이와 전년 대비',
    coach: 'chick',
  },
  {
    tab: 'focus',
    short: '집중 분야',
    title: '어디에 힘을 싣나',
    body: 'AI 키워드 · R&D · 투자 · 인력 변화',
    coach: 'owl',
  },
  {
    tab: 'comparison',
    short: '산업 비교',
    title: '업계에서 어디쯤',
    body: '동종 기업과 지표 7종 5개년 비교',
    coach: 'hamster',
  },
  {
    tab: 'issues',
    short: '최근 이슈',
    title: '요즘 무슨 일',
    body: '최근 뉴스와 중요 이슈 분류',
    coach: 'fox',
  },
];

export const QUESTION_BY_TAB = Object.fromEntries(
  COMPANY_QUESTIONS.map((q) => [q.tab, q]),
) as Record<CompanyQuestion['tab'], CompanyQuestion>;

/** "01"처럼 두 자리 번호 */
export const questionNumber = (tab: CompanyQuestion['tab']): string =>
  String(COMPANY_QUESTIONS.findIndex((q) => q.tab === tab) + 1).padStart(2, '0');
