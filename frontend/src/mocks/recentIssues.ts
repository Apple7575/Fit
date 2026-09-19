import type {
  NewsItem,
  NewsStats,
  TopNewsItem,
} from '../features/recent-issues/types';

/**
 * 백엔드 /news · /news/stats · /news/top 미구현 동안 화면 확인용 목업.
 * 삼성전자: AI 분류 포함 풀 데이터 / 현대차: AI 필드 없는 기본 뉴스만 / NAVER: 뉴스 없음.
 * api 가 category·sort·page 로 걸러 돌려준다.
 */
export const mockNewsByCompany: Record<string, NewsItem[]> = {
  '00126380': [
    {
      id: 10250,
      title: '1분기 영업이익 6.6조 원 전년 대비 931.9% 증가',
      description: '메모리 가격 회복으로 반도체 부문 실적이 크게 개선됐다.',
      publishedAt: '2025-05-20',
      originalUrl: 'https://news.example.com/10250',
      category: '실적',
      relatedBusiness: '메모리',
      importanceScore: 9.6,
    },
    {
      id: 10241,
      title: '삼성전자 텍사스 파운드리 공장 건설 본격화',
      description: '현지 생산 확대에 나선다.',
      publishedAt: '2025-05-13',
      originalUrl: 'https://news.example.com/10241',
      category: '투자',
      relatedBusiness: '파운드리',
      importanceScore: 9.2,
    },
    {
      id: 10238,
      title: 'HBM4 샘플 주요 고객사 공급 시작',
      description: '차세대 고대역폭 메모리 양산 준비에 들어갔다.',
      publishedAt: '2025-05-11',
      originalUrl: 'https://news.example.com/10238',
      category: '기술',
      relatedBusiness: 'HBM',
      importanceScore: 8.8,
    },
    {
      id: 10230,
      title: '2nm GAA 공정 로드맵 공개',
      description: null,
      publishedAt: '2025-05-09',
      originalUrl: 'https://news.example.com/10230',
      category: '기술',
      relatedBusiness: '파운드리',
      importanceScore: 8.1,
    },
    {
      id: 10222,
      title: '로봇 사업 조직 신설… 레인보우로보틱스 협력 확대',
      description: '휴머노이드 로봇 상용화를 위한 조직을 꾸렸다.',
      publishedAt: '2025-05-07',
      originalUrl: 'https://news.example.com/10222',
      category: '투자',
      relatedBusiness: '로봇',
      importanceScore: 7.4,
    },
    {
      id: 10215,
      title: '갤럭시 신제품 언팩 일정 확정',
      description: '7월 언팩에서 폴더블 신제품을 공개한다.',
      publishedAt: '2025-05-05',
      originalUrl: 'https://news.example.com/10215',
      category: '제품',
      relatedBusiness: '스마트폰',
      importanceScore: 6.3,
    },
    {
      id: 10209,
      title: '노조, 임금 협상 재개 요구',
      description: null,
      publishedAt: '2025-05-03',
      originalUrl: 'https://news.example.com/10209',
      category: '인사',
      relatedBusiness: null,
      importanceScore: 5.1,
    },
    {
      id: 10201,
      title: '유럽 에너지 라벨 규제 대응 가전 라인업 확대',
      description: '고효율 가전으로 유럽 규제에 대응한다.',
      publishedAt: '2025-05-01',
      originalUrl: 'https://news.example.com/10201',
      category: '규제',
      relatedBusiness: '가전',
      importanceScore: 4.8,
    },
  ],
  '00164742': [
    {
      id: 20010,
      title: '현대차, 울산 전기차 전용공장 착공',
      description: '2026년 양산을 목표로 한다.',
      publishedAt: '2025-05-15',
      originalUrl: 'https://news.example.com/20010',
      category: null,
      relatedBusiness: null,
      importanceScore: null,
    },
    {
      id: 20008,
      title: '1분기 판매 100만 대 돌파',
      description: null,
      publishedAt: '2025-05-02',
      originalUrl: 'https://news.example.com/20008',
      category: null,
      relatedBusiness: null,
      importanceScore: null,
    },
  ],
  '00266961': [],
};

export const mockNewsStatsByCompany: Record<string, NewsStats> = {
  '00126380': {
    kpis: {
      recentNewsCount: 48,
      recentNewsDays: 7,
      importantIssueCount: 12,
      investmentIssueCount: 5,
      techIssueCount: 7,
      issueDays: 30,
    },
    distribution: {
      days: 30,
      total: 96,
      byCategory: [
        { category: '기술', count: 28, ratio: 29.2 },
        { category: '투자', count: 20, ratio: 20.8 },
        { category: '실적', count: 18, ratio: 18.8 },
        { category: '제품', count: 14, ratio: 14.6 },
        { category: '인사', count: 9, ratio: 9.4 },
        { category: '규제', count: 7, ratio: 7.3 },
      ],
    },
  },
};

export const mockTopNewsByCompany: Record<string, TopNewsItem[]> = {
  '00126380': [
    { rank: 1, id: 10250, title: '1분기 영업이익 6.6조 원 전년 대비 931.9% 증가', category: '실적', importanceScore: 9.6 },
    { rank: 2, id: 10241, title: '삼성전자 텍사스 파운드리 공장 건설 본격화', category: '투자', importanceScore: 9.2 },
    { rank: 3, id: 10238, title: 'HBM4 샘플 주요 고객사 공급 시작', category: '기술', importanceScore: 8.8 },
  ],
};
