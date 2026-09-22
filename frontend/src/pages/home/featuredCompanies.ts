/**
 * 홈·검색 화면에서 바로 열 수 있는 기업. corpCode 는 실제 DART 고유번호이며,
 * 개발 서버에 기본정보·지표가 적재된 기업만 둔다 (없는 데이터를 있는 것처럼 보이지 않게).
 * 기업 요약 화면용 사진도 이 기업들부터 public/company-media 에 채운다.
 *
 * <p>site 는 로고를 찾는 데만 쓴다. 이 목록은 손으로 관리하는 열 곳이라 도메인을 적어 두면
 * 기업 하나마다 검색·상세를 부르지 않고도 로고를 띄울 수 있다 (CompanyLogo).
 */
export const FEATURED_COMPANIES = [
  { corpCode: '00126380', name: '삼성전자', site: 'samsung.com' },
  { corpCode: '00164779', name: 'SK하이닉스', site: 'skhynix.com' },
  { corpCode: '00164742', name: '현대자동차', site: 'hyundai.com' },
  { corpCode: '00106641', name: '기아', site: 'kia.com' },
  { corpCode: '00401731', name: 'LG전자', site: 'lge.co.kr' },
  { corpCode: '01515323', name: 'LG에너지솔루션', site: 'lgensol.com' },
  { corpCode: '00155319', name: 'POSCO홀딩스', site: 'posco-inc.com' },
  { corpCode: '00877059', name: '삼성바이오로직스', site: 'samsungbiologics.com' },
  { corpCode: '00266961', name: 'NAVER', site: 'navercorp.com' },
  { corpCode: '00258801', name: '카카오', site: 'kakaocorp.com' },
] as const;
