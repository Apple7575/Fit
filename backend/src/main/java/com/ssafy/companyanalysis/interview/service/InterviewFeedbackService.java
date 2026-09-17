package com.ssafy.companyanalysis.interview.service;

import com.ssafy.companyanalysis.interview.ai.AiEvaluation;
import com.ssafy.companyanalysis.interview.ai.AiFollowup;
import com.ssafy.companyanalysis.interview.ai.InterviewLlmClient;
import com.ssafy.companyanalysis.interview.dto.AnalyzeRequest;
import com.ssafy.companyanalysis.interview.dto.AnalyzeResponse;
import com.ssafy.companyanalysis.interview.dto.FollowupRequest;
import com.ssafy.companyanalysis.interview.dto.FollowupResponse;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/** 답변 분석(A: 내용 중심) + 꼬리질문 생성. 무저장, 로그인 전용. */
@Service
public class InterviewFeedbackService {

    private static final Set<String> KINDS = Set.of("STRENGTH", "IMPROVEMENT");
    private static final Set<String> CATEGORIES = Set.of("질문적합성", "구체성", "논리성", "기업직무이해", "전달력");
    private static final int MAX_POINTS = 4;

    private static final String ANALYZE_SYSTEM = """
            너는 한국어 면접 코치다. 아래 문항별 답변(트랜스크립트)의 '내용'을 평가한다.
            규칙:
            - items 는 입력 문항과 같은 순서·같은 개수로 만든다.
            - point 는 문항당 1~4개. 답변에서 실제로 의미 있는 강점(STRENGTH)·개선점(IMPROVEMENT)만 담고, 개수를 억지로 채우지 않는다. 강점·개선점의 개수와 비율은 답변에 따라 달라질 수 있다.
            - kind 는 STRENGTH / IMPROVEMENT 중 하나.
            - category 는 [질문적합성, 구체성, 논리성, 기업직무이해, 전달력] 중 하나.
            - message 는 무엇이 좋은지/부족한지, suggestion 은 어떻게 고치면 좋은지(개선점일 때).
            - 답변이 비어 있으면 무응답으로 보고 개선점을 준다.
            - overallSummary 는 2~3문장 총평. 점수·합불 판정은 하지 않는다.
            """;

    private static final String FOLLOWUP_SYSTEM = """
            너는 한국어 면접관이다. 지원자의 직전 답변을 듣고, 더 깊이 파고들 가치가 있을 때만 꼬리질문 1개를 만든다.
            규칙:
            - needed 는 이 답변에 추가로 더 물을 가치가 있으면 true, 아니면 false.
            - 답변이 너무 짧거나 무응답이거나 질문과 무관하거나, 더 캐물어도 의미 있는 내용이 없으면
              needed=false 로 하고 question 은 빈 문자열로 둔다. 억지로 질문을 만들지 않는다.
            - question 은 needed=true 일 때만, 답변에서 실제로 언급된 경험·기술·의사결정을 구체적으로 더 깊이 묻는 한 문장.
            - basis 는 답변의 어떤 부분에서 이 질문이 나왔는지 짧은 근거.
            - 답변에 없는 내용을 지어내지 않는다.
            """;

    private final InterviewLlmClient llmClient;

    public InterviewFeedbackService(InterviewLlmClient llmClient) {
        this.llmClient = llmClient;
    }

    public AnalyzeResponse analyze(AnalyzeRequest request) {
        AiEvaluation ai = llmClient.evaluateAnswers(ANALYZE_SYSTEM, analyzeUserText(request));

        List<AnalyzeRequest.Item> requested = request.items();
        List<AiEvaluation.AiItem> evaluated = ai.items() == null ? List.of() : ai.items();
        List<AnalyzeResponse.Item> items = java.util.stream.IntStream.range(0, requested.size())
                .mapToObj(i -> toItem(i, i < evaluated.size() ? evaluated.get(i) : null))
                .toList();

        return new AnalyzeResponse(ai.overallSummary(), items);
    }

    public FollowupResponse followup(FollowupRequest request) {
        String userText = "질문: " + request.question() + "\n답변: " + request.transcript()
                + "\n지원 직무: " + blankToDash(request.targetPosition());
        AiFollowup ai = llmClient.generateFollowup(FOLLOWUP_SYSTEM, userText);
        // 더 물을 가치가 없다고 판단(needed=false)했거나 질문이 비면 꼬리질문을 만들지 않는다(question=null).
        if (Boolean.FALSE.equals(ai.needed()) || ai.question() == null || ai.question().isBlank()) {
            return new FollowupResponse(null, null);
        }
        return new FollowupResponse(ai.question(), ai.basis());
    }

    private String analyzeUserText(AnalyzeRequest request) {
        String type = "technical".equals(request.interviewType()) ? "기술 면접" : "인성 면접";
        StringBuilder sb = new StringBuilder();
        sb.append("[면접 유형] ").append(type).append('\n');
        sb.append("[지원 직무] ").append(blankToDash(request.targetPosition())).append("\n\n");
        int n = 1;
        for (AnalyzeRequest.Item item : request.items()) {
            String transcript = (item.transcript() == null || item.transcript().isBlank())
                    ? "(무응답)" : item.transcript();
            sb.append("문항 ").append(n++).append('\n');
            sb.append("질문: ").append(item.question()).append('\n');
            sb.append("답변: ").append(transcript).append("\n\n");
        }
        return sb.toString();
    }

    private AnalyzeResponse.Item toItem(int index, AiEvaluation.AiItem evaluated) {
        if (evaluated == null) {
            return new AnalyzeResponse.Item(index + 1, "", List.of());
        }
        List<AiEvaluation.AiPoint> source = evaluated.points() == null ? List.of() : evaluated.points();
        List<AnalyzeResponse.Point> points = source.stream()
                .filter(p -> p.message() != null && !p.message().isBlank())
                .limit(MAX_POINTS)
                .map(this::toPoint)
                .toList();
        String summary = evaluated.feedbackSummary() == null ? "" : evaluated.feedbackSummary();
        return new AnalyzeResponse.Item(index + 1, summary, points);
    }

    private AnalyzeResponse.Point toPoint(AiEvaluation.AiPoint p) {
        String kind = KINDS.contains(p.kind()) ? p.kind() : "IMPROVEMENT";
        String category = CATEGORIES.contains(p.category()) ? p.category() : "질문적합성";
        return new AnalyzeResponse.Point(kind, category, p.message().strip(), p.suggestion());
    }

    private String blankToDash(String value) {
        return (value == null || value.isBlank()) ? "미지정" : value;
    }
}
