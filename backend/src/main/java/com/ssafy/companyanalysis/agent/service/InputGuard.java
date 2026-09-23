package com.ssafy.companyanalysis.agent.service;

import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * 검토 방에 들어온 사용자 발화를 AI 에 넘기기 전에 거른다.
 *
 * <p>모든 방(총괄·전담·기업·뉴스)의 발화가 {@link TurnService#start} 한 곳을 지나므로 여기서
 * 막으면 경로마다 따로 막을 필요가 없다. 모델을 부르지 않으므로 모델이 얼마나 순한지와 무관하게
 * 막히고, GMS 호출도 쓰지 않는다. AI 쪽 방어(ai/llm/prompt_guard.py, 프롬프트 규칙)는 그대로 두어
 * 여기를 빠져나간 것을 한 번 더 받는다.
 *
 * <p>위험한 요청은 대상 낱말만으로 막지 않고 "알려 줘·하는 법" 같은 요청 꼬리가 붙을 때만 막는다.
 * 낱말만 보면 자소서에 흔한 말("화약 제조 공정 경험", "개인정보 유출 사고 대응", "해킹 대회 수상")까지
 * 막힌다. 관련 없는 질문(잡담·숙제 등)은 낱말로 가를 수 없어 여기서 막지 않고, 담당 프롬프트가
 * 정해진 문장으로 거절한다.
 */
final class InputGuard {

    enum Kind { SELF_HARM, HARMFUL, JAILBREAK }

    record Verdict(Kind kind, String reply) {
    }

    static final String JAILBREAK_REPLY = "그 요청은 따르지 않습니다. 이 방은 자소서와 지원 준비를 돕는 곳이라 "
            + "지시를 바꾸거나 규칙을 우회하는 요청에는 답하지 않습니다. 자소서나 지원 공고에 대해 물어봐 주세요.";

    static final String HARMFUL_REPLY = "그 요청에는 답할 수 없습니다. 위험하거나 불법이 될 수 있는 내용은 "
            + "다루지 않습니다. 자소서나 지원 준비에 관한 질문이라면 도와드리겠습니다.";

    /** 자해 신호에는 거절이 아니라 도움받을 곳을 먼저 알린다. */
    static final String SELF_HARM_REPLY = "많이 힘드신 것 같아 걱정됩니다. 혼자 견디지 않으셨으면 합니다.\n\n"
            + "• 자살예방상담전화 109 (24시간)\n"
            + "• 정신건강위기상담전화 1577-0199\n"
            + "• 위급하면 112 또는 119\n\n"
            + "자소서 이야기는 준비되셨을 때 언제든 이어서 하실 수 있습니다.";

    private static final int FLAGS = Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE;

    /** 방법을 묻거나 해 달라고 하는 꼬리. 위험한 대상 뒤에 이것이 붙어야 요청으로 본다. */
    private static final String ASK = "[^\\n]{0,6}(는\\s*(법|방법|곳|데)|방법|법\\s*(좀\\s*)?알려|알려\\s*(줘|주세요|줄래|달라)"
            + "|가르쳐|려면|고\\s*싶|해\\s*(줘|주세요)|줘|주세요|사이트)";

    private static final List<Pattern> SELF_HARM = List.of(
            Pattern.compile("죽고\\s*싶|살기\\s*싫|사라지고\\s*싶|목숨을?\\s*끊"),
            Pattern.compile("(자살|자해)\\s*(하고\\s*싶|할래|할까|하려고|하는\\s*(법|방법)|방법)"),
            Pattern.compile("극단적(인)?\\s*선택을?\\s*(하고|할|하려)"),
            Pattern.compile("\\b(kill\\s+myself|suicide\\s+method|end\\s+my\\s+life)\\b", FLAGS));

    /** 자소서에 쓸 지난 이야기를 묻는 것이 분명하면 상담 안내로 돌리지 않는다. */
    private static final Pattern WRITING_ABOUT_PAST =
            Pattern.compile("자소서|자기소개서|문항|써도\\s*(될|되나)|쓸까|적어도\\s*(될|되나)|극복한\\s*경험");

    private static final List<Pattern> HARMFUL = List.of(
            // 무기·독극물
            Pattern.compile("(폭탄|폭발물|사제\\s*총|총기|화약|독극물|독약|신경\\s*가스|생화학\\s*무기)"
                    + "[^\\n]{0,15}(만드|제조|제작|구하|구입|사는|합성)" + ASK),
            // 마약
            Pattern.compile("(마약|필로폰|메스암페타민|대마초?|코카인|헤로인|펜타닐|엑스터시|케타민)"
                    + "[^\\n]{0,15}(만드|제조|구하|구입|사는|파는|합성|거래|재배)" + ASK),
            // 남의 계정·기기 침입. 대상(남의 계정)과 행위(해킹·알아내기)가 함께 있어야 한다.
            Pattern.compile("(남의|다른\\s*사람|타인|상대방?|친구|전\\s*(여친|남친|애인))\\s*[^\\n]{0,10}"
                    + "(계정|비밀번호|비번|카톡|메신저|메일|휴대폰|핸드폰|폰|컴퓨터)[^\\n]{0,15}"
                    + "(해킹|알아내|훔치|뚫|몰래|털)"),
            Pattern.compile("(해킹|디도스|ddos|랜섬웨어|악성\\s*코드|피싱|키로거)\\s*(하는|만드는|짜는|거는|치는)\\s*(법|방법|코드)"
                    + "|(해킹|디도스|ddos|랜섬웨어|악성\\s*코드|피싱|키로거)\\s*(방법|코드)\\s*(좀\\s*)?(알려|짜|만들|작성)",
                    FLAGS),
            // 개인정보 빼내기
            Pattern.compile("(주민\\s*(등록)?\\s*번호|개인\\s*정보|전화\\s*번호|집\\s*주소)[^\\n]{0,10}"
                    + "(알아내|캐내|빼내|훔치)" + ASK),
            // 폭력
            Pattern.compile("(죽이는|살해하는|납치하는|폭행하는)\\s*(법|방법)|(살인|청부\\s*살인|납치|테러)\\s*(방법|계획)\\s*(좀\\s*)?(알려|세워|짜)"),
            // 서류·경력 위조
            Pattern.compile("(재직|경력|졸업|성적|학위|자격증|어학\\s*성적|토익|증명서|서류)[^\\n]{0,10}"
                    + "(위조|조작|가짜로\\s*(만들|꾸며))" + ASK),
            Pattern.compile("\\bhow\\s+to\\s+(make|build)\\s+(a\\s+)?(bomb|explosive|meth|weapon)", FLAGS));

    private static final List<Pattern> JAILBREAK = List.of(
            // 아래 넷은 ai/llm/prompt_guard.py 의 패턴과 같다. 두 곳이 어긋나지 않게 함께 고친다.
            Pattern.compile("(이전|이전의|앞의|위의|기존|기존의|모든|지금까지|이제까지|여태|그동안|방금|아까|처음|원래)"
                    + "[^\\n]{0,10}(지시|명령|규칙|프롬프트|설정)[^\\n]{0,12}(무시|잊|버리|취소|없던)"
                    + "|ignore\\s+(all\\s+|the\\s+|any\\s+)?(previous|prior|above|earlier|preceding)\\s+"
                    + "(instructions?|rules?|prompts?|messages?)"
                    + "|disregard\\s+(all\\s+|the\\s+)?(previous|prior|above)", FLAGS),
            Pattern.compile("(너는|당신은|넌|니가|네가)\\s*(이제|지금부터|오늘부터|앞으로)\\s*[^\\n]{0,20}"
                    + "(이다|야|이야|담당|역할|ai|말한다|말해|행동|대답한다|답한다|굴어)"
                    + "|(지금부터|이제부터|앞으로는)\\s*(너는|당신은|넌)"
                    + "|you\\s+are\\s+now\\b|act\\s+as\\b|pretend\\s+(to\\s+be|you\\s+are)|roleplay\\s+as\\b", FLAGS),
            Pattern.compile("(시스템|system)\\s*(프롬프트|prompt|지시|instruction)[^\\n]{0,15}"
                    + "(출력|보여|알려|공개|말해|반복|print|show|reveal|repeat)", FLAGS),
            // "한 문장으로만 답해" 는 짧게 해 달라는 정상 요청이라 막지 않는다. 답의 내용을 정해 주는 것만 막는다.
            Pattern.compile("(라고만|이라고만|다고만)\\s*(답|말|출력|대답|응답)|(그대로|똑같이)\\s*(출력|따라|반복)해"),
            // 이름난 탈옥 수법
            Pattern.compile("탈옥|jailbreak|\\bdan\\s*(모드|mode|프롬프트|prompt)|do\\s+anything\\s+now"
                    + "|developer\\s+mode|개발자\\s*모드|god\\s*mode|갓\\s*모드", FLAGS),
            // AI 의 규칙을 풀라는 요구. "필터 없이 솔직하게", "글자 수 제한 없이" 는 정상 요청이라 대상을 좁힌다.
            Pattern.compile("(안전\\s*(장치|정책|규칙|필터)|가이드\\s*라인|윤리\\s*(규칙|기준)|콘텐츠\\s*정책)"
                    + "\\s*(을|를|은|는|이|가)?\\s*(없이|없다면|없는\\s*척|풀어|풀고|해제|끄고|꺼|우회|무시하고|어기|깨|벗어나)"),
            Pattern.compile("(너의|너한테|네|당신의|ai의?|모델의?)\\s*(제한|제약|규칙|검열)[^\\n]{0,6}"
                    + "(없이|없다면|풀어|풀고|해제|무시|어기|우회|벗어나)", FLAGS),
            Pattern.compile("(숨겨진|내부|원래|초기)\\s*(지시|지시문|프롬프트)[^\\n]{0,10}(보여|알려|출력|공개|말해)"
                    + "|without\\s+(any\\s+)?(restrictions|filters|guardrails)"
                    + "|(reveal|show|print)\\s+(your|the)\\s+(system\\s+)?(prompt|instructions)", FLAGS));

    private InputGuard() {
    }

    /**
     * 막아야 하는 발화면 종류와 답할 문장을 돌려준다.
     *
     * <p>자해 신호를 가장 먼저 본다. 다른 것과 겹쳐도 도움받을 곳을 알리는 쪽이 앞서야 한다.
     */
    static Optional<Verdict> screen(String text) {
        if (text == null || text.isBlank()) {
            return Optional.empty();
        }
        String body = text.toLowerCase(Locale.ROOT);
        if (matches(SELF_HARM, body) && !WRITING_ABOUT_PAST.matcher(body).find()) {
            return Optional.of(new Verdict(Kind.SELF_HARM, SELF_HARM_REPLY));
        }
        if (matches(HARMFUL, body)) {
            return Optional.of(new Verdict(Kind.HARMFUL, HARMFUL_REPLY));
        }
        if (matches(JAILBREAK, body)) {
            return Optional.of(new Verdict(Kind.JAILBREAK, JAILBREAK_REPLY));
        }
        return Optional.empty();
    }

    private static boolean matches(List<Pattern> patterns, String body) {
        return patterns.stream().anyMatch(pattern -> pattern.matcher(body).find());
    }
}
