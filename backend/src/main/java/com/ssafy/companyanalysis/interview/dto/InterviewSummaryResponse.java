package com.ssafy.companyanalysis.interview.dto;

/** 모의 면접 목록 한 건. */
public record InterviewSummaryResponse(
        Long id,
        String targetCompany,
        String targetPosition,
        String interviewType,
        int itemCount,
        String overallSummary,
        String createdAt) {
}
