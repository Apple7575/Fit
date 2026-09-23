package com.ssafy.companyanalysis.coverletter.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * 자소서 저장(신규·수정 공통) 요청.
 *
 * <p>{@code jobContextId} 는 공고 등록({@code POST /api/job-postings/contexts})에서 받은 식별자다.
 * 공고를 넣지 않았거나 등록에 실패했으면 비운다 — 공고는 선택이라 없다고 저장을 막지 않는다.
 *
 * <p>사람이 치는 칸에는 안내를 적어 둔다. 적어 두지 않으면 규칙을 그대로 읽은 기본 문구가
 * 나가는데 그 말로는 어느 칸을 어떻게 고쳐야 할지 알 수 없다(GlobalExceptionHandler 참고).
 * 화면이 먼저 짚어 주지만(프론트 validate.ts), 그 그물을 빠져나온 것이 여기서 걸린다.
 * 한계값은 validate.ts 와 같은 값이어야 한다.
 */
public record CoverLetterSaveRequest(
        @NotBlank(message = "자소서 제목을 입력해 주세요.")
        @Size(max = 120, message = "제목은 120자까지 쓸 수 있습니다.")
        String title,
        @Size(max = 120, message = "지원 회사는 120자까지 쓸 수 있습니다.")
        String targetCompany,
        @Size(max = 120, message = "지원 직무는 120자까지 쓸 수 있습니다.")
        String targetPosition,
        @Size(max = 80) String jobContextId,
        // 화면이 문항을 7개까지만 만든다(MAX_ITEMS). 여유를 두되 무한은 막는다
        @NotEmpty(message = "문항을 하나 이상 넣어 주세요.")
        @Size(max = 20, message = "문항은 20개까지 저장할 수 있습니다.")
        @Valid List<Item> items) {

    public record Item(
            @NotBlank(message = "문항의 질문을 입력해 주세요.")
            @Size(max = 500, message = "문항의 질문은 500자까지 쓸 수 있습니다.")
            String question,
            @NotBlank(message = "답변을 입력해 주세요. 빈 답변은 저장할 수 없습니다.")
            @Size(max = 4000, message = "답변은 4000자까지 저장할 수 있습니다.")
            String answer,
            @NotNull(message = "문항의 글자 수 제한을 정해 주세요.")
            @Min(value = 1, message = "글자 수 제한은 1~4000 사이로 정해 주세요.")
            @Max(value = 4000, message = "글자 수 제한은 1~4000 사이로 정해 주세요.")
            Integer charLimit) {
    }
}
