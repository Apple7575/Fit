package com.ssafy.companyanalysis.agent.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 자소서 하나를 놓고 여는 멀티에이전트 검토 방.
 *
 * <p>참여 에이전트는 연관 테이블이 아니라 {@code agents} JSONB 한 칸에 둔다. 방을 읽을 때는 늘
 * 전부 함께 읽고, 설정을 바꿀 때도 한 행만 고치면 되기 때문이다.
 */
@Entity
@Table(name = "agent_room")
public class Room {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, updatable = false)
    private Long userId;

    @Column(name = "cover_letter_id", nullable = false, updatable = false)
    private Long coverLetterId;

    /** 검토 대상 채용공고 분석(ai_job_contexts.context_id). 공고 없이 연 방은 NULL. */
    @Column(name = "job_context_id", length = 80)
    private String jobContextId;

    @Column(name = "title", length = 120, nullable = false)
    private String title;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "agents", nullable = false)
    private List<RoomAgent> agents;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "last_message_at")
    private OffsetDateTime lastMessageAt;

    protected Room() {
    }

    private Room(Long userId, Long coverLetterId, String jobContextId, String title, List<RoomAgent> agents) {
        this.userId = userId;
        this.coverLetterId = coverLetterId;
        this.jobContextId = jobContextId;
        this.title = title;
        this.agents = List.copyOf(agents);
        this.createdAt = OffsetDateTime.now();
    }

    /** 공고 없이 여는 방. 자소서를 고르면 깔아 주는 기본 방들이 이쪽이다. */
    public static Room create(Long userId, Long coverLetterId, String title, List<RoomAgent> agents) {
        return new Room(userId, coverLetterId, null, title, agents);
    }

    public static Room create(Long userId, Long coverLetterId, String jobContextId, String title,
                              List<RoomAgent> agents) {
        return new Room(userId, coverLetterId, jobContextId, title, agents);
    }

    public void rename(String title) {
        this.title = title;
    }

    public void replaceAgents(List<RoomAgent> agents) {
        this.agents = List.copyOf(agents);
    }

    public boolean ownedBy(Long candidateUserId) {
        return userId.equals(candidateUserId);
    }

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public Long getCoverLetterId() {
        return coverLetterId;
    }

    public String getJobContextId() {
        return jobContextId;
    }

    public String getTitle() {
        return title;
    }

    public List<RoomAgent> getAgents() {
        return agents == null ? List.of() : agents;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getLastMessageAt() {
        return lastMessageAt;
    }
}
