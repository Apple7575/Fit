package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.MessageListResponse;
import com.ssafy.companyanalysis.agent.dto.MessageSendRequest;
import com.ssafy.companyanalysis.agent.dto.TurnStartedResponse;
import com.ssafy.companyanalysis.agent.dto.TurnStatusResponse;
import com.ssafy.companyanalysis.agent.service.MessageQueryService;
import com.ssafy.companyanalysis.agent.service.TurnService;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** 방에 말을 걸고 진행 상황을 본다. 방에 말을 거는 것이 곧 분석이다. */
@RestController
@RequestMapping("/api/rooms/{roomId}")
public class TurnController {

    private final TurnService turnService;
    private final MessageQueryService messageQueryService;

    public TurnController(TurnService turnService, MessageQueryService messageQueryService) {
        this.turnService = turnService;
        this.messageQueryService = messageQueryService;
    }

    /** 결과를 기다리지 않고 202 로 turnId 만 준다. 진행 상황은 아래 API 로 따로 묻는다. */
    @PostMapping("/messages")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public ApiResponse<TurnStartedResponse> send(@AuthenticationPrincipal UserPrincipal principal,
                                                 @PathVariable Long roomId,
                                                 @RequestBody @Valid MessageSendRequest request) {
        return ApiResponse.ok(turnService.start(principal.getId(), roomId, request));
    }

    /** 대화 내역. 최신순 커서 페이징이라 무한 스크롤에 그대로 쓴다. */
    @GetMapping("/messages")
    public ApiResponse<MessageListResponse> messages(@AuthenticationPrincipal UserPrincipal principal,
                                                     @PathVariable Long roomId,
                                                     @RequestParam(required = false) String cursor,
                                                     @RequestParam(required = false) Integer size) {
        return ApiResponse.ok(messageQueryService.list(principal.getId(), roomId, cursor, size));
    }

    @GetMapping("/turns/{turnId}")
    public ApiResponse<TurnStatusResponse> status(@AuthenticationPrincipal UserPrincipal principal,
                                                  @PathVariable Long roomId,
                                                  @PathVariable Long turnId) {
        return ApiResponse.ok(turnService.status(principal.getId(), roomId, turnId));
    }
}
