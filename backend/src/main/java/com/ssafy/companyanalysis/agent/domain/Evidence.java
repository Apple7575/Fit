package com.ssafy.companyanalysis.agent.domain;

/**
 * 에이전트가 근거로 쓴 자료 한 건. {@code message.evidences} JSONB 의 원소다.
 *
 * <p>근거 없이 결론만 주면 사용자가 믿지 않는다. 기업 RAG·뉴스 담당처럼 외부 자료를 읽는
 * 에이전트는 무엇을 보고 말했는지 함께 남긴다.
 */
public record Evidence(String docType, String title, Integer year, Integer page, String snippet) {
}
