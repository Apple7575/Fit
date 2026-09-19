package com.ssafy.companyanalysis.agent.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 검토 방의 발화 하나.
 *
 * <p>사용자 발화와 에이전트 답변을 한 테이블에 담는다. 턴 테이블을 따로 두지 않고,
 * 사용자 발화의 id 를 턴 식별자로 쓴다({@code parentMessageId} 가 그것을 가리킨다).
 * 턴 상태는 저장하지 않고 같은 부모를 가진 행들의 상태를 모아 계산한다.
 */
@Entity
@Table(name = "agent_message")
public class Message {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "room_id", nullable = false, updatable = false)
    private Long roomId;

    /** 사용자 발화면 null. 에이전트 답변이면 딸린 사용자 발화의 id = 턴 식별자. */
    @Column(name = "parent_message_id", updatable = false)
    private Long parentMessageId;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", length = 10, nullable = false, updatable = false)
    private MessageRole role;

    @Column(name = "agent_key", length = 20, updatable = false)
    private String agentKey;

    @Column(name = "content")
    private String content;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "evidences", nullable = false)
    private List<Evidence> evidences;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "based_on", nullable = false)
    private List<Long> basedOn;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 12, nullable = false)
    private MessageStatus status;

    @Column(name = "error")
    private String error;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    protected Message() {
    }

    private Message(Long roomId, Long parentMessageId, MessageRole role, String agentKey,
                    String content, MessageStatus status) {
        this.roomId = roomId;
        this.parentMessageId = parentMessageId;
        this.role = role;
        this.agentKey = agentKey;
        this.content = content;
        this.status = status;
        this.evidences = List.of();
        this.basedOn = List.of();
        this.createdAt = OffsetDateTime.now();
    }

    /** 사용자 발화. 만들어지는 즉시 끝난 상태다. */
    public static Message fromUser(Long roomId, String content) {
        return new Message(roomId, null, MessageRole.USER, null, content, MessageStatus.DONE);
    }

    /**
     * 자동 검토 턴의 뿌리. 사용자가 아무것도 묻지 않았으므로 내용이 비어 있다.
     *
     * <p>턴은 뿌리가 있어야 성립한다(에이전트 답변이 {@code parentMessageId} 로 가리킨다).
     * 그래서 자리는 만들되 사용자가 하지 않은 말을 지어 넣지 않는다 — 화면은 내용이 빈 사용자
     * 발화를 말풍선 대신 자동 검토 표시로 그린다.
     */
    public static Message autoReview(Long roomId) {
        return new Message(roomId, null, MessageRole.USER, null, null, MessageStatus.DONE);
    }

    /** 아직 실행하지 않은 에이전트 답변 자리. 실행하면서 내용을 채운다. */
    public static Message pendingAgent(Long roomId, Long turnId, String agentKey) {
        return new Message(roomId, turnId, MessageRole.AGENT, agentKey, null, MessageStatus.PENDING);
    }

    public void markRunning() {
        this.status = MessageStatus.RUNNING;
    }

    public void succeed(String content, List<Evidence> evidences, List<Long> basedOn) {
        this.content = content;
        this.evidences = evidences == null ? List.of() : List.copyOf(evidences);
        this.basedOn = basedOn == null ? List.of() : List.copyOf(basedOn);
        this.status = MessageStatus.DONE;
        this.error = null;
    }

    /** 실패해도 턴에서 빼지 않는다. 화면에 그 자리로 남아야 사용자가 무엇이 빠졌는지 안다. */
    public void fail(String error) {
        this.status = MessageStatus.FAILED;
        this.error = error;
    }

    public Long getId() {
        return id;
    }

    public Long getRoomId() {
        return roomId;
    }

    public Long getParentMessageId() {
        return parentMessageId;
    }

    public MessageRole getRole() {
        return role;
    }

    public String getAgentKey() {
        return agentKey;
    }

    public String getContent() {
        return content;
    }

    public List<Evidence> getEvidences() {
        return evidences == null ? List.of() : evidences;
    }

    public List<Long> getBasedOn() {
        return basedOn == null ? List.of() : basedOn;
    }

    public MessageStatus getStatus() {
        return status;
    }

    public String getError() {
        return error;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
