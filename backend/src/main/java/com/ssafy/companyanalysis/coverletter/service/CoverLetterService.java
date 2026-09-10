package com.ssafy.companyanalysis.coverletter.service;

import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.domain.FeedbackComment;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterResponse;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSaveRequest;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSummaryResponse;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.coverletter.repository.FeedbackCommentRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class CoverLetterService {

    private final CoverLetterRepository coverLetterRepository;
    private final CoverLetterItemRepository itemRepository;
    private final FeedbackCommentRepository commentRepository;

    public CoverLetterService(CoverLetterRepository coverLetterRepository,
                              CoverLetterItemRepository itemRepository,
                              FeedbackCommentRepository commentRepository) {
        this.coverLetterRepository = coverLetterRepository;
        this.itemRepository = itemRepository;
        this.commentRepository = commentRepository;
    }

    @Transactional(readOnly = true)
    public List<CoverLetterSummaryResponse> list(Long userId) {
        List<CoverLetter> letters = coverLetterRepository.findByUserIdOrderByUpdatedAtDesc(userId);
        if (letters.isEmpty()) {
            return List.of();
        }
        Map<Long, List<CoverLetterItem>> itemsByLetter = itemRepository
                .findByCoverLetterIdInOrderByCoverLetterIdAscSeqAsc(letters.stream().map(CoverLetter::getId).toList())
                .stream()
                .collect(Collectors.groupingBy(CoverLetterItem::getCoverLetterId));

        return letters.stream().map(letter -> {
            List<CoverLetterItem> items = itemsByLetter.getOrDefault(letter.getId(), List.of());
            boolean hasFeedback = items.stream().anyMatch(item -> item.getFeedbackSummary() != null);
            return new CoverLetterSummaryResponse(letter.getId(), letter.getTitle(),
                    letter.getTargetCompany(), letter.getTargetPosition(),
                    items.size(), hasFeedback, letter.getUpdatedAt().toLocalDate().toString());
        }).toList();
    }

    @Transactional(readOnly = true)
    public CoverLetterResponse detail(Long userId, Long id) {
        return toResponse(findOwned(userId, id));
    }

    @Transactional
    public CoverLetterResponse create(Long userId, CoverLetterSaveRequest request) {
        CoverLetter letter = coverLetterRepository.save(
                CoverLetter.create(userId, request.title(), request.targetCompany(), request.targetPosition()));
        persistItems(letter.getId(), request.items());
        return toResponse(letter);
    }

    @Transactional
    public CoverLetterResponse update(Long userId, Long id, CoverLetterSaveRequest request) {
        CoverLetter letter = findOwned(userId, id);
        letter.update(request.title(), request.targetCompany(), request.targetPosition());
        itemRepository.deleteByCoverLetterId(id);
        persistItems(id, request.items());
        return toResponse(letter);
    }

    @Transactional
    public void delete(Long userId, Long id) {
        coverLetterRepository.delete(findOwned(userId, id));
    }

    private CoverLetter findOwned(Long userId, Long id) {
        return coverLetterRepository.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.COVER_LETTER_NOT_FOUND));
    }

    private void persistItems(Long coverLetterId, List<CoverLetterSaveRequest.Item> items) {
        for (int i = 0; i < items.size(); i++) {
            CoverLetterSaveRequest.Item source = items.get(i);
            CoverLetterItem item = CoverLetterItem.create(
                    coverLetterId, i + 1, source.question(), source.answer(), source.charLimit());

            boolean keepFeedback = feedbackMatchesAnswer(source.answer(), source.feedback());
            if (keepFeedback) {
                item.attachFeedback(source.feedback().summary() == null ? "" : source.feedback().summary());
            }
            CoverLetterItem saved = itemRepository.save(item);

            if (keepFeedback && source.feedback().comments() != null) {
                saveComments(saved.getId(), source.answer(), source.feedback().comments());
            }
        }
    }

    private void saveComments(Long itemId, String answer, List<CoverLetterSaveRequest.Comment> comments) {
        List<FeedbackComment> entities = new ArrayList<>();
        for (int j = 0; j < comments.size(); j++) {
            CoverLetterSaveRequest.Comment c = comments.get(j);
            int start = answer.indexOf(c.quote());
            Integer startOffset = start >= 0 ? start : null;
            Integer endOffset = start >= 0 ? start + c.quote().length() : null;
            entities.add(FeedbackComment.create(itemId, j + 1, c.quote(), startOffset, endOffset,
                    c.category(), c.severity(), c.message(), c.suggestion()));
        }
        commentRepository.saveAll(entities);
    }

    // 답변이 수정되면 코멘트 quote 가 더 이상 답변에 없다 → 그 문항의 피드백은 저장하지 않는다.
    private boolean feedbackMatchesAnswer(String answer, CoverLetterSaveRequest.Feedback feedback) {
        if (feedback == null) {
            return false;
        }
        if (feedback.comments() == null || feedback.comments().isEmpty()) {
            return true;
        }
        return feedback.comments().stream().allMatch(comment -> answer.contains(comment.quote()));
    }

    private CoverLetterResponse toResponse(CoverLetter letter) {
        List<CoverLetterItem> items = itemRepository.findByCoverLetterIdOrderBySeqAsc(letter.getId());
        Map<Long, List<FeedbackComment>> commentsByItem = items.isEmpty()
                ? Map.of()
                : commentRepository.findByItemIdInOrderByItemIdAscSeqAsc(items.stream().map(CoverLetterItem::getId).toList())
                        .stream().collect(Collectors.groupingBy(FeedbackComment::getItemId));

        List<CoverLetterResponse.Item> itemResponses = items.stream()
                .map(item -> new CoverLetterResponse.Item(
                        item.getQuestion(), item.getAnswer(), item.getCharLimit(),
                        toFeedback(item, commentsByItem.getOrDefault(item.getId(), List.of()))))
                .toList();

        return new CoverLetterResponse(letter.getId(), letter.getTitle(),
                letter.getTargetCompany(), letter.getTargetPosition(),
                letter.getUpdatedAt().toLocalDate().toString(), itemResponses);
    }

    private CoverLetterResponse.Feedback toFeedback(CoverLetterItem item, List<FeedbackComment> comments) {
        if (item.getFeedbackSummary() == null) {
            return null;
        }
        List<CoverLetterResponse.Comment> commentResponses = comments.stream()
                .map(c -> new CoverLetterResponse.Comment(c.getQuote(), c.getStartOffset(), c.getEndOffset(),
                        c.getCategory(), c.getSeverity(), c.getMessage(), c.getSuggestion()))
                .toList();
        return new CoverLetterResponse.Feedback(item.getFeedbackSummary(), commentResponses);
    }
}
