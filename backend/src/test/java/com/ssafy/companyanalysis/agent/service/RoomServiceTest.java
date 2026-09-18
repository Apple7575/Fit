package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.repository.JobContextRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.company.domain.Company;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.company.repository.CompanySummaryProjection;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mockito;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

class RoomServiceTest {

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
        // 저장 시점에 DB 가 채우는 id 를 흉내 낸다. 자동 검토가 방 id 로 걸리므로 필요하다.
        given(roomRepository.saveAll(any())).willAnswer(call -> {
            List<Room> rooms = call.getArgument(0);
            long id = 100;
            for (Room room : rooms) {
                org.springframework.test.util.ReflectionTestUtils.setField(room, "id", id++);
            }
            return rooms;
        });
        given(companyRepository.findAllById(any())).willAnswer(call -> {
            Iterable<String> codes = call.getArgument(0);
            return java.util.stream.StreamSupport.stream(codes.spliterator(), false)
                    .map(RoomServiceTest::company)
                    .toList();
        });

        // 이름이 정확히 걸리지 않을 때만 부른다. 부르는 테스트가 따로 채운다.
        given(companyRepository.search(any(), any())).willReturn(Page.empty());

        CoverLetter letter = Mockito.mock(CoverLetter.class);
        given(letter.getId()).willReturn(LETTER);
        given(letter.getTitle()).willReturn("2026 상반기 네이버 지원");
        given(coverLetterRepository.findByIdAndUserId(LETTER, USER)).willReturn(Optional.of(letter));
        given(coverLetterRepository.findById(LETTER)).willReturn(Optional.of(letter));
    }

    /** 이름 검색 결과 한 건. 네이티브 쿼리 프로젝션이라 인터페이스를 직접 채운다. */
    private static CompanySummaryProjection found(String corpCode, String corpName) {
        CompanySummaryProjection projection = Mockito.mock(CompanySummaryProjection.class);
        given(projection.getCorpCode()).willReturn(corpCode);
        given(projection.getCorpName()).willReturn(corpName);
        return projection;
    }

    private static Company company(String corpCode) {
        Company company = Mockito.mock(Company.class);
        given(company.getCorpCode()).willReturn(corpCode);
        given(company.getCorpName()).willReturn("00126380".equals(corpCode) ? "네이버" : "회사" + corpCode);
        return company;
    }

    private RoomService service(Set<String> indexed) {
        AgentCatalogProperties properties = new AgentCatalogProperties(indexed);
        return new RoomService(roomRepository, jobContextRepository, coverLetterRepository,
                companyRepository, new RoomAgentValidator(companyRepository, properties), properties,
                autoReviewStarter);
    }

    private RoomService service() {
        return service(Set.of());
    }

    private static RoomCreateRequest.AgentSpec spec(String key, Map<String, Object> config) {
        return new RoomCreateRequest.AgentSpec(key, config);
    }

    @Test
    @DisplayName("에이전트가 2명 이상이면 총괄이 자동으로 붙는다")
    void supervisorIsAddedWhenTwoOrMore() {
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "합동 검토", null,
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
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "글쓰기 전담", null,
                List.of(spec("writing", Map.of()))));

        assertThat(response.agents()).extracting(RoomResponse.Agent::agentKey).containsExactly("writing");
    }

    @Test
    @DisplayName("corpCodes 는 기업명과 ragReady 를 붙인 companies 로 나간다")
    void corpCodesAreEnrichedIntoCompanies() {
        RoomResponse response = service().create(USER, new RoomCreateRequest(LETTER, "기업 검토", null,
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
    @DisplayName("남의 자소서로는 방을 만들 수 없다")
    void cannotCreateRoomOnSomeoneElsesCoverLetter() {
        given(coverLetterRepository.findByIdAndUserId(LETTER, 99L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service().create(99L, new RoomCreateRequest(LETTER, "남의 자소서", null,
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

    @Test
    @DisplayName("방을 깔 때 자소서의 직무와 회사가 에이전트 설정에 그대로 들어간다")
    void defaultsCarryTheCoverLetterSettings() {
        givenCoverLetter("네이버", "서버 개발(Java/Spring)");
        Company naver = company("00126380");
        given(companyRepository.findByCorpName("네이버")).willReturn(List.of(naver));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        Map<String, Map<String, Object>> byAgent = savedSoloConfigs();
        assertThat(byAgent.get("position")).containsEntry("jobRole", "서버 개발(Java/Spring)");
        assertThat(byAgent.get("company")).containsEntry("corpCodes", List.of("00126380"));
        assertThat(byAgent.get("news")).containsEntry("corpCodes", List.of("00126380"));
    }

    @Test
    @DisplayName("채용공고 담당은 비워 둔다 — 공고 URL 을 자소서에 저장하지 않는다")
    void jobPostingAgentStaysEmpty() {
        givenCoverLetter("네이버", "서버 개발");
        Company naver = company("00126380");
        given(companyRepository.findByCorpName("네이버")).willReturn(List.of(naver));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        assertThat(savedSoloConfigs().get("jd")).isEmpty();
    }

    @Test
    @DisplayName("이름이 기업 목록에 없으면 회사는 비워 둔다 — 엉뚱한 기업을 넣지 않는다")
    void unknownCompanyNameIsLeftEmpty() {
        givenCoverLetter("이름만적은회사", "서버 개발");
        given(companyRepository.findByCorpName("이름만적은회사")).willReturn(List.of());
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        Map<String, Map<String, Object>> byAgent = savedSoloConfigs();
        assertThat(byAgent.get("company")).isEmpty();
        assertThat(byAgent.get("news")).isEmpty();
    }

    @Test
    @DisplayName("법인격 표기가 달라도 같은 기업이면 찾는다 — 공고의 \"네이버\" 와 등록명 \"네이버 주식회사\"")
    void matchesCompanyDespiteLegalFormSuffix() {
        givenCoverLetter("네이버", "서버 개발");
        CompanySummaryProjection registered = found("00126380", "네이버 주식회사");
        CompanySummaryProjection sibling = found("00999999", "네이버파이낸셜");
        given(companyRepository.findByCorpName("네이버")).willReturn(List.of());
        given(companyRepository.search(eq("네이버"), any()))
                .willReturn(new PageImpl<>(List.of(registered, sibling)));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        assertThat(savedSoloConfigs().get("company")).containsEntry("corpCodes", List.of("00126380"));
    }

    @Test
    @DisplayName("표기를 떼어 내도 둘이면 회사를 비워 둔다")
    void ambiguousAfterNormalizationIsLeftEmpty() {
        givenCoverLetter("같은이름", "서버 개발");
        CompanySummaryProjection first = found("00000001", "같은이름 주식회사");
        CompanySummaryProjection second = found("00000002", "(주)같은이름");
        given(companyRepository.findByCorpName("같은이름")).willReturn(List.of());
        given(companyRepository.search(eq("같은이름"), any()))
                .willReturn(new PageImpl<>(List.of(first, second)));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        assertThat(savedSoloConfigs().get("company")).isEmpty();
    }

    @Test
    @DisplayName("같은 이름이 여럿이면 회사를 비워 둔다 — 어느 쪽인지 알 수 없다")
    void ambiguousCompanyNameIsLeftEmpty() {
        givenCoverLetter("같은이름", "서버 개발");
        Company first = company("00000001");
        Company second = company("00000002");
        given(companyRepository.findByCorpName("같은이름")).willReturn(List.of(first, second));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        assertThat(savedSoloConfigs().get("company")).isEmpty();
    }

    @Test
    @DisplayName("이미 있는 방은 다시 채우지 않는다 — 방에서 고친 설정이 되돌아가면 안 된다")
    void existingRoomsAreNotOverwritten() {
        givenCoverLetter("네이버", "서버 개발");
        Company naver = company("00126380");
        given(companyRepository.findByCorpName("네이버")).willReturn(List.of(naver));
        Room existing = Room.create(USER, LETTER, "포지션 담당",
                List.of(new RoomAgent("position", Map.of("jobRole", "사용자가 고친 값"))));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of(existing));

        service().ensureDefaults(USER, LETTER);

        assertThat(savedSoloConfigs()).doesNotContainKey("position");
    }

    private void givenCoverLetter(String company, String position) {
        CoverLetter letter = Mockito.mock(CoverLetter.class);
        given(letter.getId()).willReturn(LETTER);
        given(letter.getTitle()).willReturn("자소서");
        given(letter.getTargetCompany()).willReturn(company);
        given(letter.getTargetPosition()).willReturn(position);
        given(coverLetterRepository.findByIdAndUserId(LETTER, USER)).willReturn(Optional.of(letter));
        given(coverLetterRepository.findById(LETTER)).willReturn(Optional.of(letter));
    }

    /** 새로 저장된 전담 방(에이전트 1명)의 설정을 agentKey 로 모은다. */
    @SuppressWarnings("unchecked")
    private Map<String, Map<String, Object>> savedSoloConfigs() {
        org.mockito.ArgumentCaptor<List<Room>> captor = org.mockito.ArgumentCaptor.forClass(List.class);
        org.mockito.Mockito.verify(roomRepository).saveAll(captor.capture());
        return captor.getValue().stream()
                .filter(room -> room.getAgents().size() == 1)
                .collect(java.util.stream.Collectors.toMap(
                        room -> room.getAgents().get(0).agentKey(),
                        room -> room.getAgents().get(0).config()));
    }

    @Test
    @DisplayName("방을 깔면 자동 검토가 걸린다 — 사용자가 무엇을 봐 달라고 적기 전에 결과가 보여야 한다")
    void defaultRoomsAreReviewedWithoutBeingAsked() {
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        ArgumentCaptor<List<Long>> captor = ArgumentCaptor.forClass(List.class);
        then(autoReviewStarter).should().startAll(eq(USER), captor.capture());
        // 전담 방 5개 + 총괄 논의 방 1개
        assertThat(captor.getValue()).hasSize(6);
    }

    @Test
    @DisplayName("총괄 논의 방을 먼저 검토한다 — 화면이 처음 여는 방이 그것이다")
    void theJointRoomIsReviewedFirst() {
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(List.of());

        service().ensureDefaults(USER, LETTER);

        ArgumentCaptor<List<Long>> captor = ArgumentCaptor.forClass(List.class);
        then(autoReviewStarter).should().startAll(eq(USER), captor.capture());
        // 만들어진 순서는 전담 방이 먼저다. 총괄 논의 방(마지막 id)이 앞으로 당겨져야 한다.
        assertThat(captor.getValue().get(0)).isEqualTo(105L);
    }

    @Test
    @DisplayName("전에 만들어져 비어 있던 방도 검토 후보로 넘긴다 — 언제 만들어졌는지는 사용자와 상관없다")
    void roomsMadeEarlierAreReviewedToo() {
        List<Room> already = new java.util.ArrayList<>(java.util.Arrays.stream(
                        new String[] {"jd", "company", "position", "news", "writing"})
                .map(key -> Room.create(USER, LETTER, key, List.of(new RoomAgent(key, Map.of()))))
                .toList());
        already.add(Room.create(USER, LETTER, "총괄 논의", List.of(
                new RoomAgent("writing", Map.of()), new RoomAgent("position", Map.of()))));
        given(roomRepository.findAllForSidebarByCoverLetter(USER, LETTER)).willReturn(already);

        service().ensureDefaults(USER, LETTER);

        ArgumentCaptor<List<Long>> captor = ArgumentCaptor.forClass(List.class);
        then(autoReviewStarter).should().startAll(eq(USER), captor.capture());
        assertThat(captor.getValue()).hasSize(6);
    }
}
