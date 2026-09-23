package com.ssafy.companyanalysis.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 방에 말을 건다. 이 한 번이 곧 분석 요청이다.
 *
 * @param coverLetterItemId 주면 그 문항만, 없으면 자소서 전체를 본다
 * @param writingReview 글쓰기 검토 버튼으로 요청한 글쓰기 전용 턴인지 여부
 */
public record MessageSendRequest(
        @NotBlank(message = "보낼 말을 입력해 주세요.")
        @Size(max = 2000, message = "한 번에 2000자까지 보낼 수 있습니다.")
        String content,
        Long coverLetterItemId,
        boolean writingReview) {

    public MessageSendRequest(String content, Long coverLetterItemId) {
        this(content, coverLetterItemId, false);
    }
}
