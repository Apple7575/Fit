package com.ssafy.companyanalysis.agent.policy;

import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public final class AgentInputPolicy {

    public static final String VERSION = "agent-policy-v1";
    public static final String SCOPE_REPLY =
            "이 방에서는 자소서와 지원 준비에 관한 질문에만 답할 수 있습니다. "
                    + "자소서나 지원 공고에 대해 물어봐 주세요.";
    public static final String INJECTION_REPLY =
            "그 요청은 따르지 않습니다. 이 방은 자소서와 지원 준비를 돕는 곳이라 "
                    + "지시를 바꾸거나 규칙을 우회하는 요청에는 답하지 않습니다. 자소서나 지원 공고에 대해 물어봐 주세요.";
    public static final String SAFETY_REPLY =
            "그 요청에는 답할 수 없습니다. 안전한 취업 준비와 자기소개서 작성에 관한 질문으로 바꿔 주세요.";
    public static final String REPHRASE_REPLY =
            "요청의 의도를 안전하게 확인하기 어렵습니다. 숨은 문자나 인코딩 없이 취업 준비와 관련된 질문을 평문으로 다시 적어 주세요.";

    private static final List<Pattern> INJECTION = List.of(
            pattern("(이전|앞의|기존|원래|지금까지).{0,20}(지시|명령|규칙|프롬프트).{0,20}(무시|잊어|버려|취소)"),
            pattern("(시스템|개발자).{0,8}(프롬프트|지시|메시지).{0,15}(출력|공개|보여|알려|반복)"),
            pattern("(개발자|dan|jailbreak|제한 없는|무제한).{0,8}(모드|ai|역할|전환)"),
            pattern("ignore.{0,12}(previous|prior|above).{0,12}(instruction|rule|prompt)"),
            pattern("reveal.{0,12}(system|developer).{0,12}(prompt|instruction|message)"),
            pattern("(base64|hex|rot13|복호화|디코딩).{0,30}(실행|따라|지시|명령)"));

    private static final List<Pattern> HARMFUL = List.of(
            pattern("(비밀번호|계정|개인정보).{0,15}(알아내|훔치|탈취|해킹)"),
            pattern("(해킹|피싱|악성코드|랜섬웨어|ddos).{0,15}(방법|코드|만들|해줘|알려)"),
            pattern("(재직|경력|졸업|성적|자격증).{0,8}(증명서)?.{0,8}(위조|조작|가짜)"),
            pattern("(폭탄|폭발물|마약|무기).{0,15}(만들|제조|구매|방법)"),
            pattern("(죽고 싶|자살|자해).{0,15}(방법|도와|알려|하고 싶)"));

    private static final List<Pattern> CAREER_RELEVANT = List.of(
            pattern("자소서|자기소개서|지원[ ]?동기|채용[ ]?공고|지원[ ]?공고|면접|이력서|포트폴리오"),
            pattern("직무|직장|취업|지원자|채용[ ]?담당|기업[ ]?분석|회사|산업|사업[ ]?보고서"),
            pattern("경험|역량|성과|강점|약점|퇴사[ ]?이유|입사[ ]?후|성장[ ]?과정"),
            pattern("문장|문항|초안|첨삭|글쓰기|글자[ ]?수|분량|표현|다듬|줄여|고쳐|검토"));

    private static final List<Pattern> OFF_TOPIC = List.of(
            pattern("(배고프|점심|저녁|아침|야식).{0,15}(추천|뭐|메뉴|먹|골라)"),
            pattern("(짜장면|라면|김치찌개|파스타|요리).{0,15}(만들|레시피|끓이|방법)"),
            pattern("(오늘|내일|주말)?.{0,8}(날씨|기온|미세먼지).{0,8}(알려|어때|뭐)"),
            pattern("(파이썬|자바|코딩|수학|과제).{0,20}(만들어|풀어|답|코드)"),
            pattern("^(욕해[ ]?봐|씨+발+|시+발+|fuck|shit)[!. ]*$"));

    private final PolicyTextNormalizer normalizer;

    public AgentInputPolicy(PolicyTextNormalizer normalizer) {
        this.normalizer = normalizer;
    }

    public PolicyDecision evaluate(String rawText, InputSource source) {
        NormalizedText normalized = normalizer.normalize(rawText);
        String body = normalized.inspectionText().toLowerCase(Locale.ROOT);
        String compact = body.replaceAll("[\\p{Z}\\p{P}\\p{S}]", "");

        if (matches(INJECTION, body) || matches(INJECTION, compact)) {
            return refuse(PolicyAction.REFUSE_INJECTION, "prompt_injection", INJECTION_REPLY);
        }
        if (matches(HARMFUL, body) || matches(HARMFUL, compact)) {
            return refuse(PolicyAction.REFUSE_SAFETY, "unsafe_request", SAFETY_REPLY);
        }
        if (matches(CAREER_RELEVANT, body)) {
            return allow();
        }
        if (matches(OFF_TOPIC, body)) {
            return refuse(PolicyAction.REFUSE_SCOPE, "off_topic", SCOPE_REPLY);
        }
        if (normalized.suspicious()) {
            return refuse(PolicyAction.NEED_REPHRASE, "obfuscated_input", REPHRASE_REPLY);
        }
        return allow();
    }

    private static boolean matches(List<Pattern> patterns, String text) {
        return patterns.stream().anyMatch(pattern -> pattern.matcher(text).find());
    }

    private static Pattern pattern(String expression) {
        return Pattern.compile(expression, Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    }

    private static PolicyDecision allow() {
        return new PolicyDecision(PolicyAction.ALLOW, "career_related", null, VERSION);
    }

    private static PolicyDecision refuse(PolicyAction action, String reason, String reply) {
        return new PolicyDecision(action, reason, reply, VERSION);
    }
}
