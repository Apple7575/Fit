package com.ssafy.companyanalysis.coverletter.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterResponse;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSaveRequest;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSummaryResponse;
import com.ssafy.companyanalysis.coverletter.service.CoverLetterService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 자소서 CRUD. 로그인 + 본인 소유 자원만 접근한다. */
@RestController
@RequestMapping("/api/cover-letters")
public class CoverLetterController {

    private final CoverLetterService coverLetterService;

    public CoverLetterController(CoverLetterService coverLetterService) {
        this.coverLetterService = coverLetterService;
    }

    @GetMapping
    public ApiResponse<List<CoverLetterSummaryResponse>> list(@AuthenticationPrincipal UserPrincipal principal) {
        return ApiResponse.ok(coverLetterService.list(principal.getId()));
    }

    @PostMapping
    public ApiResponse<CoverLetterResponse> create(@AuthenticationPrincipal UserPrincipal principal,
                                                   @RequestBody @Valid CoverLetterSaveRequest request) {
        return ApiResponse.ok(coverLetterService.create(principal.getId(), request));
    }

    @GetMapping("/{id}")
    public ApiResponse<CoverLetterResponse> detail(@AuthenticationPrincipal UserPrincipal principal,
                                                   @PathVariable Long id) {
        return ApiResponse.ok(coverLetterService.detail(principal.getId(), id));
    }

    @PutMapping("/{id}")
    public ApiResponse<CoverLetterResponse> update(@AuthenticationPrincipal UserPrincipal principal,
                                                   @PathVariable Long id,
                                                   @RequestBody @Valid CoverLetterSaveRequest request) {
        return ApiResponse.ok(coverLetterService.update(principal.getId(), id, request));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@AuthenticationPrincipal UserPrincipal principal, @PathVariable Long id) {
        coverLetterService.delete(principal.getId(), id);
        return ApiResponse.ok(null);
    }
}
