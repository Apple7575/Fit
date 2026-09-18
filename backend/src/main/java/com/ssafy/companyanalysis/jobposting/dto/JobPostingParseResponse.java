package com.ssafy.companyanalysis.jobposting.dto;

import java.util.List;

/**
 * 공고에서 읽어 낸 값. 저장하지 않고 화면 입력칸을 채우는 데만 쓴다.
 *
 * <p>{@code positions} 는 공고에 쓰인 문구를 그대로 담는다. 직무 분류 체계로 옮기지 않는다 —
 * 사용자가 자기 공고에서 본 이름 그대로 고르는 편이 헷갈리지 않는다.
 * 하나면 화면이 바로 채우고, 여럿이면 고르게 한다.
 *
 * <p>회사명을 못 찾으면 {@code companyName} 이 null 이다. 직무를 못 찾으면 빈 배열이다.
 * 둘 다 비면 서비스가 400 을 낸다.
 *
 * <p>{@code sourceKey} 는 방금 긁은 본문을 서버가 잠시 들고 있다는 표시다. 등록할 때
 * 그대로 돌려주면 공고를 다시 긁지 않는다. 보관하지 못했으면 null 이고, 그때는 등록 쪽이
 * 주소로 다시 읽는다.
 */
public record JobPostingParseResponse(
        String companyName,
        List<String> positions,
        String sourceUrl,
        String sourceKey) {
}
