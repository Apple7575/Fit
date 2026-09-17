package com.ssafy.companyanalysis.agent.domain;

/**
 * 에이전트가 방에 들어올 때 채워야 하는 설정 항목 하나.
 *
 * <p>프론트는 이 값으로 설정 UI 를 그린다. 에이전트를 추가해도 화면 코드를 고치지 않게 하려는 것이다.
 *
 * @param type        값의 모양. {@code array} · {@code enum} · {@code string} · {@code number}
 * @param required    비우고 방을 만들 수 없으면 true
 * @param description 화면에 띄울 설명
 */
public record ConfigField(String type, boolean required, String description) {
}
