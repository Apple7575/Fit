package com.ssafy.companyanalysis.jobposting.dto;

/**
 * 등록된 채용공고 분석.
 *
 * <p>{@code jobContextId} 를 검토 방 생성에 그대로 넘기면 방에 공고가 붙는다.
 *
 * <p>회사명·직무명은 AI 에 저장된 값이다. 화면이 보낸 값이 있으면 그 값이고, 비워 보냈으면
 * 공고에서 뽑힌 값이라 화면이 입력칸을 맞춰 둘 수 있다.
 */
public record JobPostingContextResponse(
        String jobContextId,
        String companyName,
        String positionName,
        String sourceUrl) {
}
