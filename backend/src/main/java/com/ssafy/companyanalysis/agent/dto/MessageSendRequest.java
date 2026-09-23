package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 방에 말을 건다. 이 한 번이 곧 분석 요청이다.
 *
 * @param coverLetterItemId 주면 그 문항만, 없으면 자소서 전체를 본다
 */
public record MessageSendRequest(
        @NotBlank(message = "보낼 말을 입력해 주세요.")
        @Size(max = 2000, message = "한 번에 2000자까지 보낼 수 있습니다.")
        String content,
        Long coverLetterItemId) {
}
