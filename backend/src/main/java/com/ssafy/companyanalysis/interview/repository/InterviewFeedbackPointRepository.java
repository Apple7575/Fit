package com.ssafy.companyanalysis.interview.repository;

import com.ssafy.companyanalysis.interview.domain.InterviewFeedbackPoint;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;

public interface InterviewFeedbackPointRepository extends JpaRepository<InterviewFeedbackPoint, Long> {

    List<InterviewFeedbackPoint> findByItemIdInOrderByItemIdAscSeqAsc(Collection<Long> itemIds);
}
