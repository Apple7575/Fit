package com.ssafy.companyanalysis.coverletter.repository;

import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface CoverLetterItemRepository extends JpaRepository<CoverLetterItem, Long> {

    List<CoverLetterItem> findByCoverLetterIdOrderBySeqAsc(Long coverLetterId);

    List<CoverLetterItem> findByCoverLetterIdInOrderByCoverLetterIdAscSeqAsc(Collection<Long> coverLetterIds);

    /** 코멘트는 FK ON DELETE CASCADE 로 함께 삭제된다. */
    @Modifying
    @Query("delete from CoverLetterItem i where i.coverLetterId = :coverLetterId")
    void deleteByCoverLetterId(@Param("coverLetterId") Long coverLetterId);
}
