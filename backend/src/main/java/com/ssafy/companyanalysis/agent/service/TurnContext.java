package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.domain.AgentType;

import java.util.List;
import java.util.Map;

/**
 * 한 턴을 도는 동안 에이전트들이 함께 보는 재료.
 *
 * <p>턴을 시작할 때 한 번 만들어 넘긴다. 에이전트마다 자소서를 다시 조회하면 같은 내용을
 * 여러 번 읽게 된다.
 *
 * <p>자소서를 붙인 본문과 문항별 조각을 같이 싣는다. 프롬프트로 도는 에이전트는 본문
 * 한 덩어리면 되지만, 포지션·글쓰기 API 는 문항과 답변을 따로 받는다.
 *
 * @param coverLetterText  문항과 답변을 붙인 본문
 * @param coverLetterParts 문항별 조각. 문항 하나만 지정한 턴에서는 한 개다
 * @param userMessage      사용자가 방에 남긴 말
 * @param jobPostingText   방에 붙은 채용공고 본문. 공고 없이 연 방은 null
 * @param agentConfigs     agentKey 별 설정(기업 선택·직무 선택)
 */
public record TurnContext(String coverLetterText,
                          List<CoverLetterPart> coverLetterParts,
                          String userMessage,
                          String jobPostingText,
                          Map<String, Map<String, Object>> agentConfigs) {

    public boolean hasJobPosting() {
        return jobPostingText != null && !jobPostingText.isBlank();
    }

    public Map<String, Object> configOf(AgentType type) {
        return agentConfigs.getOrDefault(type.key(), Map.of());
    }

    /** 아직 안 쓴 문항은 검토할 것이 없다. AI 쪽도 빈 문자열을 받지 않는다. */
    public List<CoverLetterPart> answeredParts() {
        return coverLetterParts.stream().filter(CoverLetterPart::hasAnswer).toList();
    }

    /**
     * @param charLimit 문항에 적어 둔 글자 수 제한. 안 적은 문항은 0 이다
     */
    public record CoverLetterPart(int seq, String question, String answer, int charLimit) {

        public boolean hasAnswer() {
            return answer != null && !answer.isBlank();
        }
    }
}
