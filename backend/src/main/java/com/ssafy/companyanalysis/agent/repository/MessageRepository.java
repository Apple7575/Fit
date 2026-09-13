package com.ssafy.companyanalysis.agent.repository;

import com.ssafy.companyanalysis.agent.domain.Message;
import com.ssafy.companyanalysis.agent.domain.MessageStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface MessageRepository extends JpaRepository<Message, Long> {

    /** 한 턴에 속한 에이전트 답변들. 턴 상태는 이걸 모아 계산한다. */
    List<Message> findByParentMessageIdOrderByIdAsc(Long parentMessageId);

    Optional<Message> findByIdAndRoomId(Long id, Long roomId);

    /** 아직 끝나지 않은 턴이 있는지. 방마다 한 번에 한 턴만 돈다. */
    boolean existsByRoomIdAndStatusIn(Long roomId, Collection<MessageStatus> statuses);
}
