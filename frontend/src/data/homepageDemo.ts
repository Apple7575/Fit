/**
 * 홈 랜딩의 제품 스토리(5탭 데모)에 쓰는 고정 데이터.
 * 홈이 실시간 API 여러 개에 의존해 깨지거나 스크롤 타이밍이 흔들리지 않도록 검증된 예시값만 둔다.
 * 실제 검색부터는 API 데이터를 쓴다. 숫자는 화면 설계용 예시이며 실제 공시와 다를 수 있다.
 */
export const DEMO_COMPANY = {
  corpCode: '00126380',
  name: '삼성전자',
  industry: '전기·전자제품 제조업',
  market: '유가증권시장',
  dataYear: 2025,
} as const;

export type SceneKey = 'overview' | 'growth' | 'focus' | 'comparison' | 'issues';

export interface SceneCopy {
  key: SceneKey;
  tab: string;
  title: string;
  lead: string;
  /** 스크롤을 더 내리면 나오는 보조 문구 */
  body: string;
  /** 실제 분석 화면 경로 (근거 보기) */
  path: string;
}

export const SCENES: SceneCopy[] = [
  {
    key: 'overview',
    tab: '기업소개',
    title: '먼저, 이 회사가 누구인지.',
    lead: '기업개황과 핵심 사업을 한 화면에서 확인합니다.',
    body: '설립일·대표자·소재지 같은 기본 정보와 주요 사업·제품을 출처와 함께 봅니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/overview`,
  },
  {
    key: 'growth',
    tab: '성장 분석',
    title: '회사는 정말 성장하고 있을까?',
    lead: '매출만 보면 놓칩니다.',
    body: '매출, 영업이익, 직원 수의 5년 변화를 함께 봅니다. 누락된 연도는 추정하지 않고 비워 둡니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/growth`,
  },
  {
    key: 'focus',
    tab: '집중 분야',
    title: '사람과 돈이 향한 곳이, 회사의 집중 분야입니다.',
    lead: '투자, 인력, 사업보고서의 변화를 근거와 함께 보여줍니다.',
    body: '분야명 → 어떤 변화가 있었는지 → 어느 자료에서 나왔는지 순서로 읽습니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/focus`,
  },
  {
    key: 'comparison',
    tab: '산업 비교',
    title: '좋은 숫자도, 비교해야 의미가 있습니다.',
    lead: '같은 산업의 기업들과 동일한 기준으로 나란히 비교합니다.',
    body: '같은 해, 같은 지표로만 비교합니다. 근거 없는 순위는 만들지 않습니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/comparison`,
  },
  {
    key: 'issues',
    tab: '최근 이슈',
    title: '최근 변화는 뉴스와 공시에서 먼저 보입니다.',
    lead: '같은 사건은 묶고, 날짜와 출처는 그대로 남깁니다.',
    body: '제목·날짜·원문 링크를 먼저 보여주고, 분류와 중요도는 준비된 만큼만 덧붙입니다.',
    path: `/companies/${DEMO_COMPANY.corpCode}/issues`,
  },
];

export const DEMO_OVERVIEW = {
  summary: '반도체, 모바일, 가전 사업을 함께 하는 글로벌 전자 기업',
  facts: [
    { label: '설립일', value: '1969년 1월 13일' },
    { label: '대표자', value: '한종희, 경계현' },
    { label: '소재지', value: '경기도 수원시' },
  ],
  businesses: ['반도체', '스마트폰', '가전'],
  source: 'DART 기업개황',
};

export const DEMO_GROWTH = {
  changes: [
    { label: '매출액', rate: 1.7 },
    { label: '영업이익', rate: -79.9 },
    { label: '직원 수', rate: -0.3 },
  ],
  years: [2021, 2022, 2023, 2024, 2025],
  /** 매출액(조 원) — 2023 은 예시 누락 처리 없이 전부 있음 */
  revenue: [279.6, 302.2, 258.9, 300.9, 300.9],
  source: 'DART 재무·직원현황',
};

export const DEMO_FOCUS = {
  areas: [
    {
      rank: 1,
      name: 'AI 반도체',
      signal: '높은 신호',
      evidence: '투자 확대 · 관련 언급 증가',
      sources: ['사업보고서', '뉴스', '출자현황'],
    },
    {
      rank: 2,
      name: '파운드리',
      signal: '중간 신호',
      evidence: '미국 테일러 공장 설비투자',
      sources: ['주요공시', '뉴스'],
    },
    {
      rank: 3,
      name: '로봇',
      signal: '중간 신호',
      evidence: '타법인 출자 · 조직 신설',
      sources: ['출자현황', '뉴스'],
    },
  ],
};

export const DEMO_COMPARISON = {
  industry: '전기·전자제품 제조업',
  year: 2025,
  peerCount: 3,
  rows: [
    { label: '매출 성장률', peer: 5.8, target: 1.7, unit: '%' },
    { label: '영업이익률', peer: 8.1, target: 2.2, unit: '%' },
    { label: '1인 평균 급여', peer: 1.05, target: 1.3, unit: '억 원' },
  ],
};

export const DEMO_ISSUES = [
  { date: '05.20', title: '1분기 영업이익 6.6조 원, 전년 대비 931.9% 증가', category: '실적', count: 12 },
  { date: '05.13', title: '텍사스 파운드리 공장 건설 본격화', category: '투자', count: 7 },
  { date: '05.11', title: 'HBM4 샘플 주요 고객사 공급 시작', category: '기술', count: 4 },
];

/** 홈 하단 "분석 가능한 기업" — 목업/시드에 있는 기업만 (최근 검색 데이터가 없으므로 거짓 표기 금지) */
export const DEMO_COMPANIES = [
  { corpCode: '00126380', name: '삼성전자' },
  { corpCode: '90000001', name: 'SK하이닉스' },
  { corpCode: '90000002', name: '현대차' },
  { corpCode: '90000004', name: 'NAVER' },
];
