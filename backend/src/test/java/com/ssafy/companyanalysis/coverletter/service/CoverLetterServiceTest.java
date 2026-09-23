package com.ssafy.companyanalysis.coverletter.service;

import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.dto.CoverLetterResponse;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class CoverLetterServiceTest {

    @Mock
    private CoverLetterRepository coverLetterRepository;

    @Mock
    private CoverLetterItemRepository itemRepository;

    @InjectMocks
    private CoverLetterService service;

    @Test
    void detailIncludesItemIdForTargetedReview() {
        CoverLetter letter = CoverLetter.create(7L, "상반기 지원", "회사", "백엔드", null);
        ReflectionTestUtils.setField(letter, "id", 12L);
        CoverLetterItem item = CoverLetterItem.create(12L, 1, "지원 동기", "답변", 500);
        ReflectionTestUtils.setField(item, "id", 99L);
        given(coverLetterRepository.findByIdAndUserId(12L, 7L)).willReturn(Optional.of(letter));
        given(itemRepository.findByCoverLetterIdOrderBySeqAsc(12L)).willReturn(List.of(item));

        CoverLetterResponse response = service.detail(7L, 12L);

        assertThat(response.items()).singleElement()
                .extracting(CoverLetterResponse.Item::id)
                .isEqualTo(99L);
    }
}
