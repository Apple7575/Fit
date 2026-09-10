package com.ssafy.companyanalysis.coverletter.dto;

/** 자소서 목록 한 건. */
public record CoverLetterSummaryResponse(
        Long id,
        String title,
        String targetCompany,
        String targetPosition,
        int itemCount,
        boolean hasFeedback,
        String updatedAt) {
}
