package com.ssafy.companyanalysis.comparison.repository;

/**
 * 비교 후보 기업 목록의 네이티브 쿼리 결과 한 행.
 *
 * <p>정렬 지표의 값은 담지 않는다. 정렬에만 쓰고 응답에는 실리지 않아서다.
 */
public interface IndustryCompanyProjection {

    String getCorpCode();

    String getCorpName();
}
