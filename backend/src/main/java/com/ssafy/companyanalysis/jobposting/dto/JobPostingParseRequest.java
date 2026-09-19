package com.ssafy.companyanalysis.jobposting.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 채용공고 URL 확인 요청. */
public record JobPostingParseRequest(
        @NotBlank @Size(max = 2000) String url) {
}
