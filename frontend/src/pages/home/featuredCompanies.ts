/**
 * 홈·검색 화면에서 바로 열 수 있는 기업. corpCode 는 실제 DART 고유번호이며,
 * 개발 서버에 기본정보·지표가 적재된 기업만 둔다 (없는 데이터를 있는 것처럼 보이지 않게).
 * 기업 요약 화면용 사진도 이 기업들부터 public/company-media 에 채운다.
 */
export const FEATURED_COMPANIES = [
  { corpCode: '00126380', name: '삼성전자' },
  { corpCode: '00164779', name: 'SK하이닉스' },
  { corpCode: '00164742', name: '현대자동차' },
  { corpCode: '00106641', name: '기아' },
  { corpCode: '00401731', name: 'LG전자' },
  { corpCode: '01515323', name: 'LG에너지솔루션' },
  { corpCode: '00155319', name: 'POSCO홀딩스' },
  { corpCode: '00877059', name: '삼성바이오로직스' },
  { corpCode: '00266961', name: 'NAVER' },
  { corpCode: '00258801', name: '카카오' },
] as const;
