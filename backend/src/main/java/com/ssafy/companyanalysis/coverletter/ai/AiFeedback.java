package com.ssafy.companyanalysis.coverletter.ai;

import java.util.List;

/** GMS(Gemini) 응답 파싱 형태. offset 계산은 서비스가 한다. */
public record AiFeedback(String summary, List<AiComment> comments) {

    public record AiComment(
            String quote,
            String category,
            String severity,
            String message,
            String suggestion) {
    }
}
