package com.ssafy.companyanalysis.interview.repository;

import com.ssafy.companyanalysis.interview.domain.InterviewItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;

public interface InterviewItemRepository extends JpaRepository<InterviewItem, Long> {

    List<InterviewItem> findBySessionIdOrderBySeqAsc(Long sessionId);

    List<InterviewItem> findBySessionIdInOrderBySessionIdAscSeqAsc(Collection<Long> sessionIds);

    /** 피드백 포인트는 FK ON DELETE CASCADE 로 함께 삭제된다. */
    @Modifying
    @Query("delete from InterviewItem i where i.sessionId = :sessionId")
    void deleteBySessionId(@Param("sessionId") Long sessionId);
}
