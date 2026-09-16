package com.ssafy.companyanalysis.coverletter.dto;

import java.util.List;

/** 자소서 상세(저장·조회 응답). */
public record CoverLetterResponse(
        Long id,
        String title,
        String targetCompany,
        String targetPosition,
        String updatedAt,
        List<Item> items) {

    public record Item(String question, String answer, int charLimit) {
    }
}
