package com.ssafy.companyanalysis.agent.repository;

import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface MessageRepository extends JpaRepository<Message, Long> {

    /** 한 턴에 속한 에이전트 답변들. 턴 상태는 이걸 모아 계산한다. */
    List<Message> findByParentMessageIdOrderByIdAsc(Long parentMessageId);

    Optional<Message> findByIdAndRoomId(Long id, Long roomId);

    /** 아직 끝나지 않은 턴이 있는지. 방마다 한 번에 한 턴만 돈다. */
    boolean existsByRoomIdAndStatusIn(Long roomId, Collection<MessageStatus> statuses);

    /** 말이 한 번이라도 오갔는지. 자동 검토는 빈 방에서만 돈다. */
    boolean existsByRoomId(Long roomId);

    /**
     * 대화 내역 한 페이지. 최신순이며 cursor 보다 오래된 것만 준다.
     *
     * <p>offset 페이징을 쓰지 않는 이유는, 보는 도중에 턴이 끝나 메시지가 늘면 경계가 밀려
     * 같은 메시지를 두 번 보거나 건너뛰기 때문이다.
     */
    @Query("SELECT m FROM Message m"
            + " WHERE m.roomId = :roomId"
            + "   AND (:cursor IS NULL OR m.id < :cursor)"
            + " ORDER BY m.id DESC")
    List<Message> findPage(@Param("roomId") Long roomId,
                           @Param("cursor") Long cursor,
                           Pageable pageable);
}
