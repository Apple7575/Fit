package com.ssafy.companyanalysis.coverletter.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

/** 자소서 저장(신규·수정 공통) 요청. */
public record CoverLetterSaveRequest(
        @NotBlank @Size(max = 120) String title,
        @Size(max = 120) String targetCompany,
        @Size(max = 120) String targetPosition,
        @NotEmpty @Valid List<Item> items) {

    public record Item(
            @NotBlank @Size(max = 500) String question,
            @NotBlank @Size(max = 4000) String answer,
            @NotNull @Min(1) @Max(4000) Integer charLimit) {
    }
}
