package com.ssafy.companyanalysis.jobposting.dto;

import jakarta.validation.constraints.Size;

/**
 * 채용공고 등록 요청.
 *
 * <p>회사명과 직무명은 사용자가 확인하거나 고친 값이다. 공고에서 뽑은 값을 그대로 쓸 때도
 * 화면이 실어 보낸다 — 사용자가 화면에서 본 것과 등록된 것이 어긋나지 않게 하려는 것이다.
 * 비워 두면 AI 가 공고에서 뽑은 값을 쓴다.
 *
 * <p>{@code sourceKey} 는 공고 확인 응답에서 받은 보관 키다. 주면 서버가 들고 있던 본문을
 * 그대로 등록해 공고를 다시 긁지 않는다. 없거나 보관 시간이 지났으면 주소로 다시 읽는다.
 *
 * <p>{@code url} 은 붙여넣은 이미지로 확인한 공고에는 없다. 그때는 {@code sourceKey} 로만
 * 등록하므로 둘 중 하나는 반드시 있어야 한다(서비스가 검사한다).
 */
public record JobPostingContextRequest(
        @Size(max = 2000) String url,
        @Size(max = 100) String companyName,
        @Size(max = 200) String positionName,
        @Size(max = 64) String sourceKey) {
}
