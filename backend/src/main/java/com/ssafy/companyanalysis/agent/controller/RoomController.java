package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.AgentConfigRequest;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.agent.dto.RoomDefaultsRequest;
import com.ssafy.companyanalysis.agent.dto.RoomListResponse;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.dto.RoomUpdateRequest;
import com.ssafy.companyanalysis.agent.service.RoomService;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** 자소서 검토 방. 본인 소유만 보이고 고칠 수 있다. */
@RestController
@RequestMapping("/api/rooms")
public class RoomController {

    private final RoomService roomService;

    public RoomController(RoomService roomService) {
        this.roomService = roomService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<RoomResponse> create(@AuthenticationPrincipal UserPrincipal principal,
                                            @RequestBody @Valid RoomCreateRequest request) {
        return ApiResponse.ok(roomService.create(principal.getId(), request));
    }

    /** 자소서를 고르면 에이전트 전담 방과 총괄 논의 방을 깔아 준다. 여러 번 불러도 안전하다. */
    @PostMapping("/defaults")
    public ApiResponse<RoomListResponse> ensureDefaults(@AuthenticationPrincipal UserPrincipal principal,
                                                        @RequestBody @Valid RoomDefaultsRequest request) {
        return ApiResponse.ok(roomService.ensureDefaults(principal.getId(), request.coverLetterId()));
    }

    @GetMapping
    public ApiResponse<RoomListResponse> list(@AuthenticationPrincipal UserPrincipal principal,
                                              @RequestParam(required = false) Long coverLetterId) {
        return ApiResponse.ok(roomService.list(principal.getId(), coverLetterId));
    }

    @GetMapping("/{roomId}")
    public ApiResponse<RoomResponse> detail(@AuthenticationPrincipal UserPrincipal principal,
                                            @PathVariable Long roomId) {
        return ApiResponse.ok(roomService.detail(principal.getId(), roomId));
    }

    @PatchMapping("/{roomId}")
    public ApiResponse<RoomResponse> update(@AuthenticationPrincipal UserPrincipal principal,
                                            @PathVariable Long roomId,
                                            @RequestBody @Valid RoomUpdateRequest request) {
        return ApiResponse.ok(roomService.update(principal.getId(), roomId, request));
    }

    @DeleteMapping("/{roomId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@AuthenticationPrincipal UserPrincipal principal,
                       @PathVariable Long roomId) {
        roomService.delete(principal.getId(), roomId);
    }

    /** 기업 복수 선택·직무 선택을 바꾼다. 방을 다시 만들지 않는다. */
    @PatchMapping("/{roomId}/agents/{agentKey}")
    public ApiResponse<RoomResponse.Agent> updateAgentConfig(@AuthenticationPrincipal UserPrincipal principal,
                                                             @PathVariable Long roomId,
                                                             @PathVariable String agentKey,
                                                             @RequestBody @Valid AgentConfigRequest request) {
        return ApiResponse.ok(
                roomService.updateAgentConfig(principal.getId(), roomId, agentKey, request.config()));
    }
}
