package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.NotNull;

/** 자소서 하나에 대해 기본 검토 방을 깔아 달라는 요청. */
public record RoomDefaultsRequest(@NotNull Long coverLetterId) {
}
