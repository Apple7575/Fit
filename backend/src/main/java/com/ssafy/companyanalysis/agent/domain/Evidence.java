package com.ssafy.companyanalysis.agent.domain;

/**
 * 에이전트가 근거로 쓴 자료 한 건. {@code message.evidences} JSONB 의 원소다.
 *
 * <p>근거 없이 결론만 주면 사용자가 믿지 않는다. 뉴스 담당처럼 외부 자료를 읽는 에이전트는
 * 무엇을 보고 말했는지 함께 남긴다.
 *
 * @param docType AI 가 준 근거 종류. {@code NEWS_ARTICLE} · {@code JOB_POSTING} ·
 *                {@code USER_DOCUMENT} · {@code COMPANY_REPORT}
 * @param url     기사 원문 주소. 기사가 아닌 근거는 null
 */
public record Evidence(String docType, String title, Integer year, Integer page, String snippet,
                       String url) {
}
