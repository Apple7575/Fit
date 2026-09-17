package com.ssafy.companyanalysis.interview.controller;

import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import com.ssafy.companyanalysis.interview.dto.AnalyzeRequest;
import com.ssafy.companyanalysis.interview.dto.AnalyzeResponse;
import com.ssafy.companyanalysis.interview.dto.FollowupRequest;
import com.ssafy.companyanalysis.interview.dto.FollowupResponse;
import com.ssafy.companyanalysis.interview.dto.QuestionGenerateRequest;
import com.ssafy.companyanalysis.interview.dto.QuestionGenerateResponse;
import com.ssafy.companyanalysis.interview.ratelimit.InterviewRateLimiter;
import com.ssafy.companyanalysis.interview.service.InterviewFeedbackService;
import com.ssafy.companyanalysis.interview.service.InterviewQuestionService;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 모의 면접 LLM 엔드포인트(질문 생성·답변 분석·꼬리질문). 무저장이며 로그인 사용자만 호출한다. */
@RestController
@RequestMapping("/api/interviews")
public class InterviewAiController {

    private final InterviewQuestionService questionService;
    private final InterviewFeedbackService feedbackService;
    private final InterviewRateLimiter rateLimiter;

    public InterviewAiController(InterviewQuestionService questionService,
                                 InterviewFeedbackService feedbackService,
                                 InterviewRateLimiter rateLimiter) {
        this.questionService = questionService;
        this.feedbackService = feedbackService;
        this.rateLimiter = rateLimiter;
    }

    @PostMapping("/questions")
    public ApiResponse<QuestionGenerateResponse> questions(@AuthenticationPrincipal UserPrincipal principal,
                                                           @RequestBody @Valid QuestionGenerateRequest request) {
        rateLimiter.check(principal);
        return ApiResponse.ok(questionService.generate(principal.getId(), request));
    }

    @PostMapping("/analyze")
    public ApiResponse<AnalyzeResponse> analyze(@AuthenticationPrincipal UserPrincipal principal,
                                                @RequestBody @Valid AnalyzeRequest request) {
        rateLimiter.check(principal);
        return ApiResponse.ok(feedbackService.analyze(request));
    }

    @PostMapping("/followup")
    public ApiResponse<FollowupResponse> followup(@AuthenticationPrincipal UserPrincipal principal,
                                                  @RequestBody @Valid FollowupRequest request) {
        rateLimiter.check(principal);
        return ApiResponse.ok(feedbackService.followup(request));
    }
}
