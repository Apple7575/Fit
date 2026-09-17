package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.ai.SupervisorClient;
import com.ssafy.companyanalysis.agent.domain.AgentType;

import java.util.List;
import java.util.Map;

/**
 * 한 턴을 도는 동안 담당들이 함께 보는 재료.
 *
 * <p>턴을 시작할 때 한 번 만들어 넘긴다. 담당마다 자소서를 다시 조회하면 같은 내용을 여러 번
 * 읽게 된다.
 *
 * <p>공고 본문은 싣지 않는다. AI 쪽이 {@code jobContextId} 로 자기 DB 에서 직접 꺼내 읽는다 —
 * 같은 글을 백엔드가 한 번 더 실어 보낼 이유가 없다. 다만 분석이 사라졌으면 식별자도 넘기면
 * 안 되므로, 턴을 시작할 때 실제로 있는지 확인한 값만 들어온다.
 *
 * <p>AI 총괄은 대화를 들고 있지 않다. 지난 발화를 매번 통째로 실어 보내야 문맥이 이어지므로
 * {@code conversation} 도 여기 담는다.
 *
 * @param coverLetterParts 문항별 조각. 문항 하나만 지정한 턴에서는 한 개다
 * @param userMessage      사용자가 방에 남긴 말. 그대로 총괄의 지시문이 된다
 * @param jobContextId     방에 붙은 채용공고 분석 식별자. 공고가 없거나 사라졌으면 null
 * @param jobPositionName  공고에 적힌 직무명. 포지션 담당 설정이 비었을 때 대신 쓴다
 * @param conversation     이 턴 앞의 대화. 오래된 것부터 최대 20개
 * @param agentConfigs     agentKey 별 설정(기업 선택·직무 선택)
 */
public record TurnContext(List<CoverLetterPart> coverLetterParts,
                          String userMessage,
                          String jobContextId,
                          String jobPositionName,
                          List<SupervisorClient.Turn> conversation,
                          Map<String, Map<String, Object>> agentConfigs) {

    public boolean hasJobContext() {
        return jobContextId != null && !jobContextId.isBlank();
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
