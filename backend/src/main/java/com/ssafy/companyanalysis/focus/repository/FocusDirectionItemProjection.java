package com.ssafy.companyanalysis.focus.repository;

/**
 * 사업 방향 목록 한 줄. {@code itemType} 으로 신규사업과 키워드를 가른다.
 *
 * <p>두 목록을 한 쿼리로 읽고 서비스에서 나눈다. 출처가 같은 AI 응답 하나이고 항상 함께
 * 나가므로 왕복을 둘로 늘릴 이유가 없다.
 */
public interface FocusDirectionItemProjection {

    String getItemType();

    String getItemName();
}
