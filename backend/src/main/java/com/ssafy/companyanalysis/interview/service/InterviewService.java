package com.ssafy.companyanalysis.interview.service;

import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.interview.domain.InterviewFeedbackPoint;
import com.ssafy.companyanalysis.interview.domain.InterviewItem;
import com.ssafy.companyanalysis.interview.domain.InterviewSession;
import com.ssafy.companyanalysis.interview.dto.InterviewResponse;
import com.ssafy.companyanalysis.interview.dto.InterviewSaveRequest;
import com.ssafy.companyanalysis.interview.dto.InterviewSummaryResponse;
import com.ssafy.companyanalysis.interview.repository.InterviewFeedbackPointRepository;
import com.ssafy.companyanalysis.interview.repository.InterviewItemRepository;
import com.ssafy.companyanalysis.interview.repository.InterviewSessionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/** 모의 면접 CRUD. 로그인 + 본인 소유만 접근하며, 저장 후 수정하지 않는다(불변). */
@Service
public class InterviewService {

    private final InterviewSessionRepository sessionRepository;
    private final InterviewItemRepository itemRepository;
    private final InterviewFeedbackPointRepository pointRepository;
    private final CoverLetterRepository coverLetterRepository;

    public InterviewService(InterviewSessionRepository sessionRepository,
                            InterviewItemRepository itemRepository,
                            InterviewFeedbackPointRepository pointRepository,
                            CoverLetterRepository coverLetterRepository) {
        this.sessionRepository = sessionRepository;
        this.itemRepository = itemRepository;
        this.pointRepository = pointRepository;
        this.coverLetterRepository = coverLetterRepository;
    }

    @Transactional(readOnly = true)
    public List<InterviewSummaryResponse> list(Long userId) {
        List<InterviewSession> sessions = sessionRepository.findByUserIdOrderByCreatedAtDesc(userId);
        if (sessions.isEmpty()) {
            return List.of();
        }
        Map<Long, List<InterviewItem>> itemsBySession = itemRepository
                .findBySessionIdInOrderBySessionIdAscSeqAsc(sessions.stream().map(InterviewSession::getId).toList())
                .stream()
                .collect(Collectors.groupingBy(InterviewItem::getSessionId));

        return sessions.stream().map(session -> new InterviewSummaryResponse(
                session.getId(), session.getTargetCompany(), session.getTargetPosition(),
                session.getInterviewType(),
                itemsBySession.getOrDefault(session.getId(), List.of()).size(),
                session.getOverallSummary(),
                session.getCreatedAt().toLocalDate().toString())).toList();
    }

    @Transactional(readOnly = true)
    public InterviewResponse detail(Long userId, Long id) {
        return toResponse(findOwned(userId, id));
    }

    @Transactional
    public InterviewResponse create(Long userId, InterviewSaveRequest request) {
        Long coverLetterId = resolveCoverLetter(userId, request.coverLetterId());
        InterviewSession session = sessionRepository.save(InterviewSession.create(
                userId, request.targetCompany(), request.targetPosition(), request.interviewType(),
                coverLetterId, request.overallSummary()));
        persistItems(session.getId(), request.items());
        return toResponse(session);
    }

    @Transactional
    public void delete(Long userId, Long id) {
        sessionRepository.delete(findOwned(userId, id));
    }

    private InterviewSession findOwned(Long userId, Long id) {
        return sessionRepository.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INTERVIEW_NOT_FOUND));
    }

    /** 연동 자소서가 본인 소유일 때만 기록한다. 아니면 null(연동 없음). */
    private Long resolveCoverLetter(Long userId, Long coverLetterId) {
        if (coverLetterId == null) {
            return null;
        }
        return coverLetterRepository.findByIdAndUserId(coverLetterId, userId).isPresent() ? coverLetterId : null;
    }

    private void persistItems(Long sessionId, List<InterviewSaveRequest.Item> items) {
        for (int i = 0; i < items.size(); i++) {
            InterviewSaveRequest.Item source = items.get(i);
            String sourceType = source.sourceType() == null ? "common" : source.sourceType();
            String transcript = source.transcript() == null ? "" : source.transcript();

            InterviewItem item = InterviewItem.create(sessionId, i + 1, source.question(), sourceType, transcript);
            if (source.feedbackSummary() != null) {
                item.attachFeedback(source.feedbackSummary());
            }
            InterviewItem saved = itemRepository.save(item);
            savePoints(saved.getId(), source.points());
        }
    }

    private void savePoints(Long itemId, List<InterviewSaveRequest.Point> points) {
        if (points == null || points.isEmpty()) {
            return;
        }
        List<InterviewFeedbackPoint> entities = new ArrayList<>();
        for (int j = 0; j < points.size(); j++) {
            InterviewSaveRequest.Point p = points.get(j);
            entities.add(InterviewFeedbackPoint.create(itemId, j + 1, p.kind(), p.category(), p.message(), p.suggestion()));
        }
        pointRepository.saveAll(entities);
    }

    private InterviewResponse toResponse(InterviewSession session) {
        List<InterviewItem> items = itemRepository.findBySessionIdOrderBySeqAsc(session.getId());
        Map<Long, List<InterviewFeedbackPoint>> pointsByItem = items.isEmpty()
                ? Map.of()
                : pointRepository.findByItemIdInOrderByItemIdAscSeqAsc(items.stream().map(InterviewItem::getId).toList())
                        .stream().collect(Collectors.groupingBy(InterviewFeedbackPoint::getItemId));

        List<InterviewResponse.Item> itemResponses = items.stream()
                .map(item -> new InterviewResponse.Item(
                        item.getSeq(), item.getQuestion(), item.getSourceType(),
                        item.getTranscript(), item.getFeedbackSummary(),
                        toPoints(pointsByItem.getOrDefault(item.getId(), List.of()))))
                .toList();

        return new InterviewResponse(
                session.getId(), session.getTargetCompany(), session.getTargetPosition(),
                session.getInterviewType(), session.getOverallSummary(),
                session.getCreatedAt().toLocalDate().toString(), itemResponses);
    }

    private List<InterviewResponse.Point> toPoints(List<InterviewFeedbackPoint> points) {
        return points.stream()
                .map(p -> new InterviewResponse.Point(p.getKind(), p.getCategory(), p.getMessage(), p.getSuggestion()))
                .toList();
    }
}
