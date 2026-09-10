package com.ssafy.companyanalysis.coverletter.service;

import com.ssafy.companyanalysis.coverletter.ai.AiFeedback;
import com.ssafy.companyanalysis.coverletter.ai.GmsFeedbackClient;
import com.ssafy.companyanalysis.coverletter.dto.FeedbackRequest;
import com.ssafy.companyanalysis.coverletter.dto.FeedbackResponse;
import org.springframework.stereotype.Service;

import java.util.List;

/** 문항 AI 피드백(무저장). quote 로 answer 내 위치(offset)를 계산하고, 못 찾으면 null 로 둔다. */
@Service
public class FeedbackService {

    private static final int MAX_COMMENTS = 6;

    private final GmsFeedbackClient gmsFeedbackClient;

    public FeedbackService(GmsFeedbackClient gmsFeedbackClient) {
        this.gmsFeedbackClient = gmsFeedbackClient;
    }

    public FeedbackResponse feedback(FeedbackRequest request) {
        AiFeedback ai = gmsFeedbackClient.generate(
                request.question(), request.answer(), request.charLimit(), request.targetPosition());

        String answer = request.answer();
        List<AiFeedback.AiComment> source = ai.comments() == null ? List.of() : ai.comments();
        List<FeedbackResponse.Comment> comments = source.stream()
                .filter(comment -> comment.quote() != null && !comment.quote().isBlank())
                .limit(MAX_COMMENTS)
                .map(comment -> toComment(answer, comment))
                .toList();

        return new FeedbackResponse(ai.summary(), comments);
    }

    private FeedbackResponse.Comment toComment(String answer, AiFeedback.AiComment comment) {
        int start = answer.indexOf(comment.quote());
        Integer startOffset = start >= 0 ? start : null;
        Integer endOffset = start >= 0 ? start + comment.quote().length() : null;
        return new FeedbackResponse.Comment(
                comment.quote(), startOffset, endOffset,
                comment.category(), comment.severity(), comment.message(), comment.suggestion());
    }
}
