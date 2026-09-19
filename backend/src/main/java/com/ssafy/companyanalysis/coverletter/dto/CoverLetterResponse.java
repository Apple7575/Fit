package com.ssafy.companyanalysis.coverletter.dto;

import java.util.List;

/**
 * 자소서 상세(저장·조회 응답).
 *
 * <p>{@code jobContextId} 는 이 자소서에 붙은 공고 분석이다. 공고가 없으면 null. 자소서를 다시
 * 열어 고칠 때 화면이 이 값을 그대로 돌려보내야 공고가 떨어지지 않는다.
 */
public record CoverLetterResponse(
        Long id,
        String title,
        String targetCompany,
        String targetPosition,
        String jobContextId,
        String updatedAt,
        List<Item> items) {

    public record Item(String question, String answer, int charLimit) {
    }
}
