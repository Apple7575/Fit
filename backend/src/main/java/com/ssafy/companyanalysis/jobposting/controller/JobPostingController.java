package com.ssafy.companyanalysis.jobposting.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingContextRequest;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingContextResponse;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseRequest;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseResponse;
import com.ssafy.companyanalysis.jobposting.ratelimit.JobPostingRateLimiter;
import com.ssafy.companyanalysis.jobposting.service.JobPostingContextService;
import com.ssafy.companyanalysis.jobposting.service.JobPostingParseService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * 채용공고 URL 확인과 등록.
 *
 * <p>확인은 자소서 작성 화면이 회사·직무를 채우는 데 쓰며 로그인 없이 부를 수 있다.
 * 등록은 그렇게 확인한 공고를 AI 에 넘겨 검토 방에 붙일 식별자를 받는 것이라 로그인이 필요하다.
 */
@RestController
@RequestMapping("/api/job-postings")
public class JobPostingController {

    private final JobPostingParseService parseService;
    private final JobPostingContextService contextService;
    private final JobPostingRateLimiter rateLimiter;

    public JobPostingController(JobPostingParseService parseService,
                                JobPostingContextService contextService,
                                JobPostingRateLimiter rateLimiter) {
        this.parseService = parseService;
        this.contextService = contextService;
        this.rateLimiter = rateLimiter;
    }

    @PostMapping("/parse")
    public ApiResponse<JobPostingParseResponse> parse(@AuthenticationPrincipal UserPrincipal principal,
                                                      HttpServletRequest httpRequest,
                                                      @RequestBody @Valid JobPostingParseRequest request) {
        rateLimiter.check(principal, httpRequest);
        return ApiResponse.ok(parseService.parse(request.url()));
    }

    /**
     * 확인한 공고를 등록해 검토 방에 붙일 식별자를 받는다. 요구사항까지 정리하므로 확인보다
     * 무겁다 — 같은 횟수 제한을 건다.
     */
    @PostMapping("/contexts")
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<JobPostingContextResponse> register(@AuthenticationPrincipal UserPrincipal principal,
                                                           HttpServletRequest httpRequest,
                                                           @RequestBody @Valid JobPostingContextRequest request) {
        rateLimiter.check(principal, httpRequest);
        return ApiResponse.ok(contextService.register(
                request.url(), request.companyName(), request.positionName(), request.sourceKey()));
    }
}
