package com.ssafy.companyanalysis.interview.repository;

import com.ssafy.companyanalysis.interview.domain.InterviewSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface InterviewSessionRepository extends JpaRepository<InterviewSession, Long> {

    List<InterviewSession> findByUserIdOrderByCreatedAtDesc(Long userId);

    /** 소유권까지 확인. 없거나 타인 것이면 empty → 404 처리. */
    Optional<InterviewSession> findByIdAndUserId(Long id, Long userId);
}
