package com.ssafy.companyanalysis.coverletter.service;

import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterResponse;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSaveRequest;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterSummaryResponse;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class CoverLetterService {

    private final CoverLetterRepository coverLetterRepository;
    private final CoverLetterItemRepository itemRepository;

    public CoverLetterService(CoverLetterRepository coverLetterRepository,
                              CoverLetterItemRepository itemRepository) {
        this.coverLetterRepository = coverLetterRepository;
        this.itemRepository = itemRepository;
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

        return letters.stream().map(letter -> new CoverLetterSummaryResponse(
                letter.getId(), letter.getTitle(),
                letter.getTargetCompany(), letter.getTargetPosition(),
                itemsByLetter.getOrDefault(letter.getId(), List.of()).size(),
                letter.getUpdatedAt().toLocalDate().toString())).toList();
    }

    @Transactional(readOnly = true)
    public CoverLetterResponse detail(Long userId, Long id) {
        return toResponse(findOwned(userId, id));
    }

    @Transactional
    public CoverLetterResponse create(Long userId, CoverLetterSaveRequest request) {
        CoverLetter letter = coverLetterRepository.save(
                CoverLetter.create(userId, request.title(), request.targetCompany(),
                        request.targetPosition(), request.jobContextId()));
        persistItems(letter.getId(), request.items());
        return toResponse(letter);
    }

    @Transactional
    public CoverLetterResponse update(Long userId, Long id, CoverLetterSaveRequest request) {
        CoverLetter letter = findOwned(userId, id);
        letter.update(request.title(), request.targetCompany(), request.targetPosition(),
                request.jobContextId());
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
            itemRepository.save(CoverLetterItem.create(
                    coverLetterId, i + 1, source.question(), source.answer(), source.charLimit()));
        }
    }

    private CoverLetterResponse toResponse(CoverLetter letter) {
        List<CoverLetterResponse.Item> itemResponses = itemRepository
                .findByCoverLetterIdOrderBySeqAsc(letter.getId()).stream()
                .map(item -> new CoverLetterResponse.Item(item.getQuestion(), item.getAnswer(), item.getCharLimit()))
                .toList();

        return new CoverLetterResponse(letter.getId(), letter.getTitle(),
                letter.getTargetCompany(), letter.getTargetPosition(), letter.getContextId(),
                letter.getUpdatedAt().toLocalDate().toString(), itemResponses);
    }
}
