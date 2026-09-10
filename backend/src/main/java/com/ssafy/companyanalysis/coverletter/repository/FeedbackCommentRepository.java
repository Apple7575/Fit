package com.ssafy.companyanalysis.coverletter.repository;

import com.ssafy.companyanalysis.coverletter.domain.FeedbackComment;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface FeedbackCommentRepository extends JpaRepository<FeedbackComment, Long> {

    List<FeedbackComment> findByItemIdInOrderByItemIdAscSeqAsc(Collection<Long> itemIds);
}
