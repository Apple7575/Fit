package com.ssafy.companyanalysis.focus.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * 집중 분야의 사업 방향·R&D 응답. 명세의 필드와 이름·순서가 같다.
 *
 * <p>두 블록의 출처가 다르다. {@code direction} 은 AI 분석 결과이고 {@code rnd} 는
 * 공시 수치다. 화면이 앞의 것만 "AI 분석"으로 구분해 표시하므로 한 블록으로 합치지 않는다.
 *
 * <p>값이 하나도 없어도 두 블록을 null 로 바꾸지 않는다. 목록은 빈 배열, 수치는 null 이며
 * 키는 그대로 남는다(docs/decisions/0001-missing-data-response.md 규칙 2·4). 조건부 영역을
 * 숨길지는 화면이 판단한다 — 서버는 사실만 내려보낸다.
 *
 * <p>{@code year} 는 이 분석과 수치가 어느 해 것인지다. 적재가 하나도 없으면 null 이다.
 */
public record CompanyFocusResponse(
        Integer year,
        Direction direction,
        Rnd rnd
) {

    /**
     * 사업 방향. AI 분석 결과이며 공시 수치가 아니다.
     *
     * <p>{@code newBusiness} 와 {@code keywords} 는 AI 가 낸 순서를 유지한다. 중요도 순으로
     * 오므로 이름순으로 다시 정렬하면 뜻이 사라진다.
     */
    public record Direction(List<String> newBusiness, List<String> keywords, String strategyChange) {
    }

    /**
     * R&D 지표. 공시 수치다.
     *
     * <p>{@code expense} 와 {@code revenueRatio} 는 지표 카탈로그의 rd_cost·rd_ratio 에서
     * 그대로 온다. {@code growthRate} 만 전년 비용과 비교해 조회 시점에 만든다.
     *
     * <p>{@code fields} 는 사업보고서의 연구개발 실적에서 오는 분야 이름 목록이다.
     */
    public record Rnd(BigDecimal expense, BigDecimal growthRate, BigDecimal revenueRatio,
                      List<String> fields) {
    }
}
