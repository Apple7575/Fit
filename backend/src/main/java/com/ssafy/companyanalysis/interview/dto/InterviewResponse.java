package com.ssafy.companyanalysis.interview.dto;

import java.util.List;

/** 모의 면접 상세(저장·조회 응답). items 순서는 면접 진행 순서다. */
public record InterviewResponse(
        Long id,
        String targetCompany,
        String targetPosition,
        String interviewType,
        String overallSummary,
        String createdAt,
        List<Item> items) {

    public record Item(
            int seq,
            String question,
            String sourceType,
            String transcript,
            String feedbackSummary,
            List<Point> points) {
    }

    public record Point(String kind, String category, String message, String suggestion) {
    }
}
