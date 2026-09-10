package com.ssafy.companyanalysis.coverletter.dto;

import java.util.List;

/** 문항 피드백 결과. offset 은 answer 내 위치이며, 없으면 프론트가 quote 로 찾는다. */
public record FeedbackResponse(String summary, List<Comment> comments) {

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
