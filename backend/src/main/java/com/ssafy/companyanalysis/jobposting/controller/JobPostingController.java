package com.ssafy.companyanalysis.jobposting.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseRequest;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseResponse;
import com.ssafy.companyanalysis.jobposting.ratelimit.JobPostingRateLimiter;
import com.ssafy.companyanalysis.jobposting.service.JobPostingParseService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 채용공고 URL 확인. 자소서 작성 화면이 회사·직무를 채우는 데 쓰며 로그인 없이 부를 수 있다. */
@RestController
@RequestMapping("/api/job-postings")
public class JobPostingController {

    private final JobPostingParseService parseService;
    private final JobPostingRateLimiter rateLimiter;

    public JobPostingController(JobPostingParseService parseService, JobPostingRateLimiter rateLimiter) {
        this.parseService = parseService;
        this.rateLimiter = rateLimiter;
    }

    @PostMapping("/parse")
    public ApiResponse<JobPostingParseResponse> parse(@AuthenticationPrincipal UserPrincipal principal,
                                                      HttpServletRequest httpRequest,
                                                      @RequestBody @Valid JobPostingParseRequest request) {
        rateLimiter.check(principal, httpRequest);
        return ApiResponse.ok(parseService.parse(request.url()));
    }
}
