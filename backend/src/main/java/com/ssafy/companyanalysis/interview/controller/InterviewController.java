package com.ssafy.companyanalysis.interview.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.interview.dto.InterviewResponse;
import com.ssafy.companyanalysis.interview.dto.InterviewSaveRequest;
import com.ssafy.companyanalysis.interview.dto.InterviewSummaryResponse;
import com.ssafy.companyanalysis.interview.service.InterviewService;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 모의 면접 CRUD. 로그인 + 본인 소유만 접근한다. 저장 후 수정하지 않아 PUT 은 없다. */
@RestController
@RequestMapping("/api/interviews")
public class InterviewController {

    private final InterviewService interviewService;

    public InterviewController(InterviewService interviewService) {
        this.interviewService = interviewService;
    }

    @GetMapping
    public ApiResponse<List<InterviewSummaryResponse>> list(@AuthenticationPrincipal UserPrincipal principal) {
        return ApiResponse.ok(interviewService.list(principal.getId()));
    }

    @PostMapping
    public ApiResponse<InterviewResponse> create(@AuthenticationPrincipal UserPrincipal principal,
                                                 @RequestBody @Valid InterviewSaveRequest request) {
        return ApiResponse.ok(interviewService.create(principal.getId(), request));
    }

    @GetMapping("/{id}")
    public ApiResponse<InterviewResponse> detail(@AuthenticationPrincipal UserPrincipal principal,
                                                 @PathVariable Long id) {
        return ApiResponse.ok(interviewService.detail(principal.getId(), id));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@AuthenticationPrincipal UserPrincipal principal, @PathVariable Long id) {
        interviewService.delete(principal.getId(), id);
        return ApiResponse.ok(null);
    }
}
