/** 검색 결과 한 건. 백엔드 CompanySummaryResponse 와 필드명이 같다. */
export type Company = {
  /** DART 고유번호 8자리. 상세 화면 URL 과 지표 API 에 사용한다. */
  corpCode: string;
  corpName: string;
  /** 종목코드 6자리. 비상장이면 없다. */
  stockCode: string | null;
  industryCode: string | null;
  industryName: string | null;
};
