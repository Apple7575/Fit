package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.AgentCatalogResponse;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.agent.dto.RoomListResponse;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.dto.RoomUpdateRequest;
import com.ssafy.companyanalysis.agent.repository.JobContextRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.data.domain.Page;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

/**
 * 구현이 덜 된 담당을 화면에서만 잠시 감추는 스위치({@code app.agent.hidden-agents}).
 *
 * <p><b>기능을 떼는 것이 아니라 가리는 것이다.</b> 서버 API 도 AI 워커도 그대로 돌고, 방에
 * 저장된 담당 목록도 그대로 남는다 — 설정만 되돌리면 QA 중에 만들어지고 고쳐진 방까지
 * 원래대로 돌아와야 하기 때문이다.
 *
 * <p>턴에서 자리를 안 만드는 것까지가 "화면에서 안 보인다" 에 들어간다. 담당 목록에서만
 * 감추면 총괄 논의 방에서 그 담당의 말풍선이 그대로 떠, 목록에 없는 담당이 답하는 꼴이 된다.
 */
class HiddenAgentTest {

    private static final Long USER = 7L;
    private static final Long LETTER = 12L;

    private RoomRepository roomRepository;
    private JobContextRepository jobContextRepository;
    private CoverLetterRepository coverLetterRepository;
    private CompanyRepository companyRepository;
    private AutoReviewStarter autoReviewStarter;

    @BeforeEach
    void setUp() {
        roomRepository = Mockito.mock(RoomRepository.class);
        jobContextRepository = Mockito.mock(JobContextRepository.class);
        coverLetterRepository = Mockito.mock(CoverLetterRepository.class);
        companyRepository = Mockito.mock(CompanyRepository.class);
        autoReviewStarter = Mockito.mock(AutoReviewStarter.class);

        given(roomRepository.save(any(Room.class))).willAnswer(call -> call.getArgument(0));
        given(companyRepository.findAllById(any())).willReturn(List.of());
        given(companyRepository.search(any(), any())).willReturn(Page.empty());

        CoverLetter letter = Mockito.mock(CoverLetter.class);
        given(letter.getId()).willReturn(LETTER);
        given(letter.getTitle()).willReturn("2026 상반기 네이버 지원");
        given(coverLetterRepository.findByIdAndUserId(LETTER, USER)).willReturn(Optional.of(letter));
        given(coverLetterRepository.findById(LETTER)).willReturn(Optional.of(letter));
    }

    private AgentCatalogProperties withoutNews() {
        return new AgentCatalogProperties(Set.of(), Set.of("news"));
    }

    private RoomService roomService(AgentCatalogProperties properties) {
        return new RoomService(roomRepository, jobContextRepository, coverLetterRepository,
                companyRepository, new RoomAgentValidator(companyRepository, properties), properties,
                autoReviewStarter);
    }

    private Room room(Long id, String title, String... agentKeys) {
        Room room = Room.create(USER, LETTER, title,
                java.util.Arrays.stream(agentKeys).map(key -> new RoomAgent(key, Map.of())).toList());
        org.springframework.test.util.ReflectionTestUtils.setField(room, "id", id);
        return room;
    }

    @Test
    @DisplayName("감춘 담당만 있는 전담 방은 목록에서 빠진다 — 들어가 봐야 아무도 답하지 않는다")
    void soloRoomOfHiddenAgentIsNotListed() {
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of(
                room(1L, "뉴스/트렌드 담당", "news"),
                room(2L, "글쓰기 담당", "writing")));

        RoomListResponse response = roomService(withoutNews()).list(USER, LETTER);

        assertThat(response.rooms()).extracting(RoomListResponse.Room::title)
                .containsExactly("글쓰기 담당");
    }

    @Test
    @DisplayName("감춘 담당을 뺀 수만 센다 — 목록의 인원수와 방 안의 말풍선 수가 어긋나면 안 된다")
    void listCountsOnlyVisibleAgents() {
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of(
                room(3L, "총괄 논의", "jd", "company", "position", "news", "writing")));

        RoomListResponse response = roomService(withoutNews()).list(USER, LETTER);

        // 담당 4명 + 총괄. 뉴스를 세면 6이 되어 방 안과 어긋난다.
        assertThat(response.rooms()).singleElement()
                .extracting(RoomListResponse.Room::agentCount).isEqualTo(5);
    }

    @Test
    @DisplayName("합동 방 상세에서 감춘 담당은 빠져 나온다")
    void hiddenAgentIsNotShownInRoomDetail() {
        Room stored = room(3L, "총괄 논의", "jd", "news", "writing");
        given(roomRepository.findByIdAndUserId(3L, USER)).willReturn(Optional.of(stored));

        RoomResponse response = roomService(withoutNews()).detail(USER, 3L);

        assertThat(response.agents()).extracting(RoomResponse.Agent::agentKey)
                .containsExactly("jd", "writing", "supervisor");
    }

    @Test
    @DisplayName("방을 고쳐도 감춘 담당은 저장된 자리에 남는다 — 다시 켜면 돌아와야 한다")
    void editingARoomKeepsTheHiddenAgentStored() {
        Room stored = room(3L, "총괄 논의", "jd", "news", "writing");
        given(roomRepository.findByIdAndUserId(3L, USER)).willReturn(Optional.of(stored));

        // 화면은 뉴스를 못 보므로 고친 목록에도 실어 보내지 못한다.
        roomService(withoutNews()).update(USER, 3L, new RoomUpdateRequest(null,
                List.of(new RoomCreateRequest.AgentSpec("jd", Map.of()))));

        assertThat(stored.getAgents()).extracting(RoomAgent::agentKey)
                .containsExactlyInAnyOrder("jd", "news");
    }

    @Test
    @DisplayName("카탈로그는 감춘 담당을 목록에 남기되 고를 수 없다고 표시한다")
    void catalogMarksTheHiddenAgentUnselectable() {
        AgentCatalogResponse response = new AgentCatalogService(withoutNews()).listAgents();

        // 목록에서 통째로 빼면 그 담당이 붙어 있는 옛 방의 말풍선을 화면이 못 읽는다.
        assertThat(response.agents()).extracting(AgentCatalogResponse.Agent::agentKey)
                .contains("news");
        assertThat(response.agents())
                .filteredOn(agent -> "news".equals(agent.agentKey()))
                .singleElement()
                .extracting(AgentCatalogResponse.Agent::selectable).isEqualTo(false);
        assertThat(response.agents())
                .filteredOn(agent -> "writing".equals(agent.agentKey()))
                .singleElement()
                .extracting(AgentCatalogResponse.Agent::selectable).isEqualTo(true);
    }

    @Test
    @DisplayName("아무것도 안 감추면 전부 그대로다 — 기본값은 다 보이는 상태다")
    void nothingIsHiddenWhenTheSwitchIsEmpty() {
        AgentCatalogProperties allVisible = new AgentCatalogProperties(Set.of());
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of(
                room(1L, "뉴스/트렌드 담당", "news")));

        assertThat(allVisible.isAgentVisible("news")).isTrue();
        assertThat(roomService(allVisible).list(USER, LETTER).rooms()).hasSize(1);
    }
}
