import type { Company } from '../types/company';

/**
 * API 연동 전까지 사용하는 임시 기업 목록이다.
 * 업종 표기는 화면 확인용 단순 분류이며 S15P21A504-14 에서 실제 응답으로 대체된다.
 */
export const mockCompanies: Company[] = [
  { code: '005930', name: '삼성전자', industry: '반도체' },
  { code: '000660', name: 'SK하이닉스', industry: '반도체' },
  { code: '005380', name: '현대차', industry: '자동차' },
  { code: '000270', name: '기아', industry: '자동차' },
  { code: '035420', name: 'NAVER', industry: '인터넷 서비스' },
  { code: '035720', name: '카카오', industry: '인터넷 서비스' },
  { code: '373220', name: 'LG에너지솔루션', industry: '2차전지' },
  { code: '207940', name: '삼성바이오로직스', industry: '바이오' },
];

/** 목업에서 오류 화면을 확인하기 위한 키워드다. 실제 API 연동 시 함께 사라진다. */
export const MOCK_ERROR_KEYWORD = '오류';

const MOCK_DELAY_MS = 300;

const normalize = (value: string) => value.replace(/\s/g, '').toLowerCase();

const delay = (ms: number) =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

/** 실제 검색 API 를 대신하는 임시 함수다. S15P21A504-14 에서 API 호출로 교체한다. */
export const searchMockCompanies = async (
  keyword: string,
): Promise<Company[]> => {
  await delay(MOCK_DELAY_MS);

  if (normalize(keyword) === normalize(MOCK_ERROR_KEYWORD)) {
    throw new Error('목업 검색에 실패했습니다');
  }

  const normalizedKeyword = normalize(keyword);

  return mockCompanies.filter(
    (company) =>
      normalize(company.name).includes(normalizedKeyword) ||
      company.code.startsWith(normalizedKeyword),
  );
};
