package com.ssafy.companyanalysis.interview.dto;

import java.util.List;

/** 생성된 면접 질문. 배열 순서가 면접 진행 순서다. */
public record QuestionGenerateResponse(List<Question> questions) {

    public record Question(int seq, String question, String sourceType) {
    }
}
