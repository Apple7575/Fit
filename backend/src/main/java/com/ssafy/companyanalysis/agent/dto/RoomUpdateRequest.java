package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.Size;

import java.util.List;

/** 검토 방 수정. 보낸 필드만 바꾼다. 둘 다 null 이면 아무것도 바꾸지 않는다. */
public record RoomUpdateRequest(
        @Size(max = 120) String title,
        List<RoomCreateRequest.AgentSpec> agents) {
}
