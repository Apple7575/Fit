import type { Company } from '../types/company';

/**
 * 백엔드 검색 API 없이 화면을 확인하기 위한 임시 데이터다.
 * corpCode 는 실제 DART 고유번호다 (개발 서버에 적재된 기업과 같다).
 * S15P21A504-12 백엔드 검색 API 가 develop 에 들어오면 이 파일은 필요 없다.
 */
export const mockCompanies: Company[] = [
  {
    corpCode: '00126380',
    corpName: '삼성전자',
    stockCode: '005930',
    industryCode: '264',
    industryName: '반도체 제조업',
  },
  {
    corpCode: '00164779',
    corpName: 'SK하이닉스',
    stockCode: '000660',
    industryCode: '264',
    industryName: '반도체 제조업',
  },
  {
    corpCode: '00164742',
    corpName: '현대자동차',
    stockCode: '005380',
    industryCode: '301',
    industryName: '자동차 제조업',
  },
  {
    corpCode: '00106641',
    corpName: '기아',
    stockCode: '000270',
    industryCode: '301',
    industryName: '자동차 제조업',
  },
  {
    corpCode: '00266961',
    corpName: 'NAVER',
    stockCode: '035420',
    industryCode: '582',
    industryName: '온라인 정보 서비스업',
  },
  {
    corpCode: '00258801',
    corpName: '카카오',
    stockCode: '035720',
    industryCode: '582',
    industryName: '온라인 정보 서비스업',
  },
  {
    corpCode: '01515323',
    corpName: 'LG에너지솔루션',
    stockCode: '373220',
    industryCode: '272',
    industryName: '전지 제조업',
  },
  {
    corpCode: '00877059',
    corpName: '삼성바이오로직스',
    stockCode: '207940',
    industryCode: '211',
    industryName: '의약품 제조업',
  },
];

/** 목업에서 오류 화면을 확인하기 위한 키워드다. 실제 API 로 전환되면 함께 사라진다. */
export const MOCK_ERROR_KEYWORD = '오류';

const normalize = (value: string) => value.replace(/\s/g, '').toLowerCase();

/** 백엔드와 같은 기준으로 기업명 부분일치 또는 코드 앞자리 일치를 확인한다. */
export const matchesMockCompany = (company: Company, keyword: string) => {
  const normalized = normalize(keyword);

  return (
    normalize(company.corpName).includes(normalized) ||
    company.corpCode.startsWith(normalized) ||
    (company.stockCode?.startsWith(normalized) ?? false)
  );
};
