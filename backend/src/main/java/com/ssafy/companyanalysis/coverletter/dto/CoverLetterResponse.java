package com.ssafy.companyanalysis.coverletter.dto;

import java.util.List;

/** 자소서 상세(저장·조회 응답). 미첨삭 문항의 feedback 은 null. */
public record CoverLetterResponse(
        Long id,
        String title,
        String targetCompany,
        String targetPosition,
        String updatedAt,
        List<Item> items) {

    public record Item(String question, String answer, int charLimit, Feedback feedback) {
    }

    public record Feedback(String summary, List<Comment> comments) {
    }

    public record Comment(
            String quote,
            Integer startOffset,
            Integer endOffset,
            String category,
            String severity,
            String message,
            String suggestion) {
    }
}
