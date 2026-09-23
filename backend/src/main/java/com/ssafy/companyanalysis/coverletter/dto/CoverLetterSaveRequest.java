package com.ssafy.companyanalysis.coverletter.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * 자소서 저장(신규·수정 공통) 요청.
 *
 * <p>{@code jobContextId} 는 공고 등록({@code POST /api/job-postings/contexts})에서 받은 식별자다.
 * 공고를 넣지 않았거나 등록에 실패했으면 비운다 — 공고는 선택이라 없다고 저장을 막지 않는다.
 */
public record CoverLetterSaveRequest(
        @NotBlank @Size(max = 120) String title,
        @Size(max = 120) String targetCompany,
        @Size(max = 120) String targetPosition,
        @Size(max = 80) String jobContextId,
        // 화면이 문항을 7개까지만 만든다(MAX_ITEMS). 여유를 두되 무한은 막는다
        @NotEmpty @Size(max = 20) @Valid List<Item> items) {

    public record Item(
            @NotBlank @Size(max = 500) String question,
            @NotBlank @Size(max = 4000) String answer,
            @NotNull @Min(1) @Max(4000) Integer charLimit) {
    }
}
