package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.company.domain.Company;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

class RoomServiceTest {

    private static final Long USER = 7L;
    private static final Long LETTER = 12L;

    private RoomRepository roomRepository;
    private CoverLetterRepository coverLetterRepository;
    private CompanyRepository companyRepository;

    @BeforeEach
    void setUp() {
        roomRepository = Mockito.mock(RoomRepository.class);
        coverLetterRepository = Mockito.mock(CoverLetterRepository.class);
        companyRepository = Mockito.mock(CompanyRepository.class);

        given(roomRepository.save(any(Room.class))).willAnswer(call -> call.getArgument(0));
        given(companyRepository.findAllById(any())).willAnswer(call -> {
            Iterable<String> codes = call.getArgument(0);
            return java.util.stream.StreamSupport.stream(codes.spliterator(), false)
                    .map(RoomServiceTest::company)
                    .toList();
        });

        CoverLetter letter = Mockito.mock(CoverLetter.class);
        given(letter.getId()).willReturn(LETTER);
        given(letter.getTitle()).willReturn("2026 상반기 네이버 지원");
        given(coverLetterRepository.findByIdAndUserId(LETTER, USER)).willReturn(Optional.of(letter));
        given(coverLetterRepository.findById(LETTER)).willReturn(Optional.of(letter));
    }

    private static Company company(String corpCode) {
        Company company = Mockito.mock(Company.class);
        given(company.getCorpCode()).willReturn(corpCode);
        given(company.getCorpName()).willReturn("00126380".equals(corpCode) ? "네이버" : "회사" + corpCode);
        return company;
    }

    private RoomService service(Set<String> readyRoles, Set<String> indexed) {
        AgentCatalogProperties properties = new AgentCatalogProperties(readyRoles, indexed);
        return new RoomService(roomRepository, coverLetterRepository, companyRepository,
                new RoomAgentValidator(companyRepository, properties), properties);
    }

    private RoomService service() {
        return service(Set.of("backend"), Set.of());
    }

    private static RoomCreateRequest.AgentSpec spec(String key, Map<String, Object> config) {
        return new RoomCreateRequest.AgentSpec(key, config);
    }

    @Test
    @DisplayName("에이전트가 2명 이상이면 총괄이 자동으로 붙는다")
    void supervisorIsAddedWhenTwoOrMore() {
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "합동 검토",
                List.of(spec("writing", Map.of()), spec("position", Map.of("jobRole", "backend")))));

        assertThat(response.agents()).extracting(RoomResponse.Agent::agentKey)
                .containsExactly("writing", "position", "supervisor");
        assertThat(response.agents()).filteredOn(RoomResponse.Agent::auto)
                .extracting(RoomResponse.Agent::agentKey)
                .containsExactly("supervisor");
    }

    @Test
    @DisplayName("에이전트가 1명인 전담 방에는 총괄이 붙지 않는다 — 조정할 것이 없다")
    void supervisorIsNotAddedForSoloRoom() {
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "글쓰기 전담",
                List.of(spec("writing", Map.of()))));

        assertThat(response.agents()).extracting(RoomResponse.Agent::agentKey).containsExactly("writing");
    }

    @Test
    @DisplayName("corpCodes 는 기업명과 ragReady 를 붙인 companies 로 나간다")
    void corpCodesAreEnrichedIntoCompanies() {
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "기업 검토",
                List.of(spec("company", Map.of("corpCodes", List.of("00126380"))))));

        Map<String, Object> config = response.agents().get(0).config();
        assertThat(config).doesNotContainKey("corpCodes");
        assertThat(config.get("companies")).isInstanceOf(List.class);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> companies = (List<Map<String, Object>>) config.get("companies");
        assertThat(companies).singleElement().satisfies(one -> {
            assertThat(one).containsEntry("corpCode", "00126380");
            assertThat(one).containsEntry("name", "네이버");
            assertThat(one).containsEntry("ragReady", true);
        });
    }

    @Test
    @DisplayName("지식베이스가 없는 직무를 고르면 그 에이전트는 ready=false 다")
    void agentIsNotReadyWhenJobRoleHasNoKnowledgeBase() {
        RoomResponse response = service(Set.of("backend"), Set.of())
                .create(USER, new RoomCreateRequest(LETTER, "데이터 직무",
                        List.of(spec("position", Map.of("jobRole", "data")))));

        assertThat(response.agents()).singleElement()
                .satisfies(agent -> assertThat(agent.ready()).isFalse());
    }

    @Test
    @DisplayName("남의 자소서로는 방을 만들 수 없다")
    void cannotCreateRoomOnSomeoneElsesCoverLetter() {
        given(coverLetterRepository.findByIdAndUserId(LETTER, 99L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service().create(99L, new RoomCreateRequest(LETTER, "남의 자소서",
                List.of(spec("writing", Map.of())))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.COVER_LETTER_NOT_FOUND);
    }

    @Test
    @DisplayName("남의 방은 404 ROOM_NOT_FOUND")
    void otherUsersRoomIsNotFound() {
        given(roomRepository.findByIdAndUserId(31L, USER)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service().detail(USER, 31L))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.ROOM_NOT_FOUND);
    }

    @Test
    @DisplayName("방에 없는 에이전트의 설정은 바꿀 수 없다")
    void cannotConfigureAgentThatIsNotInRoom() {
        Room room = Room.create(USER, LETTER, "글쓰기 전담", List.of(new RoomAgent("writing", Map.of())));
        given(roomRepository.findByIdAndUserId(31L, USER)).willReturn(Optional.of(room));

        assertThatThrownBy(() -> service().updateAgentConfig(USER, 31L, "company",
                Map.of("corpCodes", List.of("00126380"))))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.AGENT_NOT_IN_ROOM);
    }

    @Test
    @DisplayName("기업 선택을 바꾸면 그 에이전트만 갈리고 나머지는 그대로다")
    void changingOneAgentConfigLeavesOthersAlone() {
        Room room = Room.create(USER, LETTER, "합동", List.of(
                new RoomAgent("company", Map.of("corpCodes", List.of("00126380"))),
                new RoomAgent("writing", Map.of())));
        given(roomRepository.findByIdAndUserId(31L, USER)).willReturn(Optional.of(room));

        RoomResponse.Agent changed = service().updateAgentConfig(USER, 31L, "company",
                Map.of("corpCodes", List.of("00164779")));

        assertThat(changed.agentKey()).isEqualTo("company");
        assertThat(room.getAgents()).extracting(RoomAgent::agentKey).containsExactly("company", "writing");
        assertThat(room.getAgents().get(0).config()).containsEntry("corpCodes", List.of("00164779"));
        assertThat(room.getAgents().get(1).config()).isEmpty();
    }

    @Test
    @DisplayName("에이전트를 전부 빼는 수정은 막는다")
    void cannotRemoveEveryAgent() {
        Room room = Room.create(USER, LETTER, "합동", List.of(new RoomAgent("writing", Map.of())));
        given(roomRepository.findByIdAndUserId(31L, USER)).willReturn(Optional.of(room));

        assertThatThrownBy(() -> service().update(USER, 31L,
                new com.ssafy.companyanalysis.agent.dto.RoomUpdateRequest(null, List.of())))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_PARAMETER);
    }

    @Test
    @DisplayName("목록의 에이전트 수에는 자동으로 붙는 총괄도 들어간다")
    void listCountsSupervisor() {
        Room solo = Room.create(USER, LETTER, "전담", List.of(new RoomAgent("writing", Map.of())));
        Room joint = Room.create(USER, LETTER, "합동", List.of(
                new RoomAgent("writing", Map.of()), new RoomAgent("jd", Map.of("jdUrl", "https://x"))));
        given(roomRepository.findAllForSidebar(USER))
                .willReturn(List.of(solo, joint));

        assertThat(service().list(USER, null).rooms())
                .extracting(r -> r.agentCount())
                .containsExactly(1, 3);
    }

    @Test
    @DisplayName("대화 테이블이 아직 없어 목록의 미리보기는 null, running 은 false 다")
    void previewAndRunningAreNotFilledYet() {
        Room room = Room.create(USER, LETTER, "전담", List.of(new RoomAgent("writing", Map.of())));
        given(roomRepository.findAllForSidebar(USER))
                .willReturn(List.of(room));

        assertThat(service().list(USER, null).rooms()).singleElement().satisfies(one -> {
            assertThat(one.lastMessagePreview()).isNull();
            assertThat(one.running()).isFalse();
        });
    }
}
