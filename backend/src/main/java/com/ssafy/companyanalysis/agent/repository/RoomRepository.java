package com.ssafy.companyanalysis.agent.repository;

import com.ssafy.companyanalysis.agent.domain.Room;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface RoomRepository extends JpaRepository<Room, Long> {

    /**
     * 사이드바용. 대화가 없는 방(last_message_at NULL)은 뒤로 보내고 그 안에서는 최신 생성순이다.
     *
     * <p>메서드 이름으로는 표현할 수 없어 JPQL 로 쓴다 — Spring Data 의 파생 쿼리 문법에
     * {@code NullsLast} 가 없다.
     */
    @Query("""
            SELECT r FROM Room r
             WHERE r.userId = :userId
             ORDER BY r.lastMessageAt DESC NULLS LAST, r.id DESC
            """)
    List<Room> findAllForSidebar(@Param("userId") Long userId);

    @Query("""
            SELECT r FROM Room r
             WHERE r.userId = :userId
               AND r.coverLetterId = :coverLetterId
             ORDER BY r.lastMessageAt DESC NULLS LAST, r.id DESC
            """)
    List<Room> findAllForSidebarByCoverLetter(@Param("userId") Long userId,
                                              @Param("coverLetterId") Long coverLetterId);

    Optional<Room> findByIdAndUserId(Long id, Long userId);
}
