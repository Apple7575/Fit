package com.ssafy.companyanalysis.coverletter.repository;

import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface CoverLetterRepository extends JpaRepository<CoverLetter, Long> {

    List<CoverLetter> findByUserIdOrderByUpdatedAtDesc(Long userId);

    /** 소유권까지 확인. 없거나 타인 것이면 empty → 404 처리. */
    Optional<CoverLetter> findByIdAndUserId(Long id, Long userId);
}
