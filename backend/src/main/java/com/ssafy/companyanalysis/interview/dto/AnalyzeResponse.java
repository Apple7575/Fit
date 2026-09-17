package com.ssafy.companyanalysis.interview.dto;

import java.util.List;

/** 답변 분석 결과. items 순서는 요청 문항 순서와 같다. */
public record AnalyzeResponse(String overallSummary, List<Item> items) {

    public record Item(int seq, String feedbackSummary, List<Point> points) {
    }

    public record Point(String kind, String category, String message, String suggestion) {
    }
}
