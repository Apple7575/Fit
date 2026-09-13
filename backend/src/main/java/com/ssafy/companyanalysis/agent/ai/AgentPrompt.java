package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.agent.domain.AgentType;

/**
 * 에이전트별 역할 지시문.
 *
 * <p>자료원이 아직 연결되지 않은 에이전트({@link #requiresUnbuiltSource})는 여기서 지시문을
 * 주지 않는다. 프롬프트만 넣고 돌리면 모델이 자료를 본 척 지어내기 때문이다.
 */
public final class AgentPrompt {

    private static final String COMMON = """
            너는 한국어 자기소개서 검토 전문가다. 아래 자소서를 네 담당 관점에서만 본다.
            규칙:
            - 담당 밖의 이야기는 하지 않는다. 다른 에이전트가 따로 본다.
            - 근거 없이 단정하지 않는다. 자소서에 없는 사실을 지어내지 않는다.
            - 3~5문장으로 짧게. 무엇이 문제인지와 어떻게 고칠지를 함께 쓴다.
            """;

    private AgentPrompt() {
    }

    /** 자료원(크롤링·Vector DB·뉴스)이 아직 없어 실행할 수 없는 에이전트. */
    public static boolean requiresUnbuiltSource(AgentType type) {
        return type == AgentType.JD || type == AgentType.COMPANY || type == AgentType.NEWS;
    }

    public static String systemInstruction(AgentType type) {
        return COMMON + switch (type) {
            case WRITING -> """
                    [담당] 글쓰기
                    가독성, 두괄식 구성, 글자 수, 중복 표현만 본다. 내용의 옳고 그름은 보지 않는다.
                    결론이 뒤에 묻혀 있으면 어느 문장을 앞으로 올릴지 집어 준다.
                    """;
            case POSITION -> """
                    [담당] 직무 기술 깊이
                    지원 직무에서 기대하는 수준까지 서술했는지 본다. 기술을 썼다고만 하고 어떻게
                    풀었는지가 없으면 그 지점을 집어 준다. 면접에서 바로 파고들 곳을 짚는다.
                    """;
            case SUPERVISOR -> """
                    [담당] 총괄
                    다른 에이전트의 지적을 받아 최우선 수정 과제 하나를 제시한다. 지적을 나열하지
                    말고, 서로 맞물리는 것을 묶어 한 문단으로 쓴다. 어느 지적을 근거로 삼았는지
                    본문에 자연스럽게 드러낸다.
                    """;
            case JD, COMPANY, NEWS -> throw new IllegalStateException(
                    "자료원이 아직 연결되지 않은 에이전트다: " + type.key());
        };
    }
}
