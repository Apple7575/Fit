package com.ssafy.companyanalysis.coverletter.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.coverletter.dto.FeedbackRequest;
import com.ssafy.companyanalysis.coverletter.dto.FeedbackResponse;
import com.ssafy.companyanalysis.coverletter.ratelimit.FeedbackRateLimiter;
import com.ssafy.companyanalysis.coverletter.service.FeedbackService;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 자소서 문항 AI 피드백. 로그인 없이 호출 가능하며 아무것도 저장하지 않는다. */
@RestController
@RequestMapping("/api/cover-letters")
public class FeedbackController {

    private final FeedbackService feedbackService;
    private final FeedbackRateLimiter rateLimiter;

    public FeedbackController(FeedbackService feedbackService, FeedbackRateLimiter rateLimiter) {
        this.feedbackService = feedbackService;
        this.rateLimiter = rateLimiter;
    }

    @PostMapping("/feedback")
    public ApiResponse<FeedbackResponse> feedback(@AuthenticationPrincipal UserPrincipal principal,
                                                  HttpServletRequest httpRequest,
                                                  @RequestBody @Valid FeedbackRequest request) {
        rateLimiter.check(principal, httpRequest);
        return ApiResponse.ok(feedbackService.feedback(request));
    }
}
