package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.agent.config.AgentCatalogProperties;
import com.ssafy.companyanalysis.agent.domain.AgentType;
import com.ssafy.companyanalysis.agent.domain.JobContext;
import com.ssafy.companyanalysis.agent.domain.Room;
import com.ssafy.companyanalysis.agent.domain.RoomAgent;
import com.ssafy.companyanalysis.agent.dto.RoomCreateRequest;
import com.ssafy.companyanalysis.agent.dto.RoomListResponse;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.dto.RoomUpdateRequest;
import com.ssafy.companyanalysis.agent.repository.JobContextRepository;
import com.ssafy.companyanalysis.agent.repository.RoomRepository;
import com.ssafy.companyanalysis.company.domain.Company;
import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.company.repository.CompanySummaryProjection;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * 검토 방을 만들고 관리한다.
 *
 * <p>총괄(supervisor)은 저장하지 않고 읽을 때 붙인다. 저장해 두면 사용자가 에이전트를 고칠 때마다
 * 넣고 빼기를 맞춰야 하는데, 규칙은 "2명 이상이면 붙는다" 하나뿐이라 파생이 더 안전하다.
 */
@Service
@Transactional(readOnly = true)
public class RoomService {

    private final RoomRepository roomRepository;
    private final JobContextRepository jobContextRepository;
    private final CoverLetterRepository coverLetterRepository;
    private final CompanyRepository companyRepository;
    private final RoomAgentValidator validator;
    private final AgentCatalogProperties properties;

    public RoomService(RoomRepository roomRepository,
                       JobContextRepository jobContextRepository,
                       CoverLetterRepository coverLetterRepository,
                       CompanyRepository companyRepository,
                       RoomAgentValidator validator,
                       AgentCatalogProperties properties) {
        this.roomRepository = roomRepository;
        this.jobContextRepository = jobContextRepository;
        this.coverLetterRepository = coverLetterRepository;
        this.companyRepository = companyRepository;
        this.validator = validator;
        this.properties = properties;
    }

    @Transactional
    public RoomResponse create(Long userId, RoomCreateRequest request) {
        CoverLetter coverLetter = ownedCoverLetter(userId, request.coverLetterId());
        List<RoomAgent> agents = validator.validateAll(request.agents());
        String jobContextId = existingJobContextId(request.jobContextId());
        Room saved = roomRepository.save(
                Room.create(userId, coverLetter.getId(), jobContextId, request.title().trim(), agents));
        return toDetail(saved, coverLetter);
    }

    /**
     * 자소서를 고르면 대화할 자리를 미리 깔아 준다. 에이전트마다 전담 방 하나씩과 합동 논의 방
     * 하나를 만든다. 사용자가 방을 하나씩 만들어야 한다면 첫 화면부터 할 일이 생긴다.
     *
     * <p>여러 번 불러도 안전하다. 이미 있는 조합은 건너뛴다.
     */
    @Transactional
    public RoomListResponse ensureDefaults(Long userId, Long coverLetterId) {
        CoverLetter coverLetter = ownedCoverLetter(userId, coverLetterId);
        List<Room> existing = roomRepository.findAllForSidebarByCoverLetter(userId, coverLetterId);

        List<AgentType> selectable = Arrays.stream(AgentType.values())
                .filter(AgentType::selectable)
                .toList();

        List<Room> created = new ArrayList<>();
        for (AgentType type : selectable) {
            boolean already = existing.stream().anyMatch(room -> isSoloRoomFor(room, type));
            if (!already) {
                created.add(Room.create(userId, coverLetterId, type.displayName(),
                        List.of(new RoomAgent(type.key(), defaultConfig(type, coverLetter)))));
            }
        }
        if (existing.stream().noneMatch(room -> room.getAgents().size() >= 2)) {
            created.add(Room.create(userId, coverLetterId, "총괄 논의",
                    selectable.stream()
                            .map(type -> new RoomAgent(type.key(), defaultConfig(type, coverLetter)))
                            .toList()));
        }
        roomRepository.saveAll(created);

        return list(userId, coverLetterId);
    }

    /**
     * 방을 처음 깔 때 자소서에 적힌 값을 그대로 넣어 준다. 자소서에서 회사와 직무를 이미
     * 골랐는데 방에서 또 고르게 하면 같은 일을 두 번 시키는 것이다.
     *
     * <p><b>이미 있는 방은 건드리지 않는다.</b> 이 메서드는 방을 만들 때만 불린다 —
     * 목록을 열 때마다 덮어쓰면 사용자가 방에서 고친 설정이 되돌아간다.
     *
     * <p>채용공고 담당은 비워 둔다. 공고 URL 을 자소서에 저장하지 않아 넘길 값이 없다.
     */
    private Map<String, Object> defaultConfig(AgentType type, CoverLetter coverLetter) {
        return switch (type) {
            case POSITION -> {
                String jobRole = coverLetter.getTargetPosition();
                yield jobRole == null || jobRole.isBlank() ? Map.of() : Map.of("jobRole", jobRole);
            }
            case COMPANY, NEWS -> corpCodeOf(coverLetter.getTargetCompany())
                    .<Map<String, Object>>map(code -> Map.of("corpCodes", List.of(code)))
                    .orElseGet(Map::of);
            default -> Map.of();
        };
    }

    /** 이름이 흔들리는 폭을 감당할 만큼만 본다. 더 늘리면 엉뚱한 기업이 섞일 자리가 넓어진다. */
    private static final int NAME_CANDIDATE_LIMIT = 20;

    /**
     * 자소서에 적힌 회사 이름으로 기업코드를 찾는다. 하나로 좁혀질 때만 쓴다 — 여럿이면 어느
     * 쪽인지 알 수 없고, 엉뚱한 기업을 넣는 것보다 비워 두는 편이 낫다.
     *
     * <p>공고에 쓰인 이름과 DART 등록명은 법인격 표기에서 자주 어긋난다("네이버" 대
     * "네이버 주식회사"). 완전 일치로만 보면 공고에서 그대로 가져온 이름인데도 못 찾는다.
     * 그래서 한 번 더 본다: 법인격 표기와 공백을 떼어 낸 형태가 정확히 같은 기업이 하나면 그것을 쓴다.
     */
    private Optional<String> corpCodeOf(String companyName) {
        if (companyName == null || companyName.isBlank()) {
            return Optional.empty();
        }
        String raw = companyName.trim();
        List<Company> exact = companyRepository.findByCorpName(raw);
        if (exact.size() == 1) {
            return Optional.of(exact.get(0).getCorpCode());
        }
        if (!exact.isEmpty()) {
            // 같은 이름이 여럿이면 표기를 떼어 봐야 더 좁혀지지 않는다.
            return Optional.empty();
        }
        return byNormalizedName(raw);
    }

    private Optional<String> byNormalizedName(String raw) {
        String core = normalizeCompanyName(raw);
        if (core.isBlank()) {
            return Optional.empty();
        }
        List<CompanySummaryProjection> matched = companyRepository
                .search(core, PageRequest.of(0, NAME_CANDIDATE_LIMIT))
                .getContent().stream()
                .filter(company -> normalizeCompanyName(company.getCorpName()).equals(core))
                .toList();
        return matched.size() == 1
                ? Optional.of(matched.get(0).getCorpCode())
                : Optional.empty();
    }

    /** 법인격 표기와 공백·점을 떼어 낸 형태. 영문 이름을 위해 소문자로 맞춘다. */
    private static String normalizeCompanyName(String name) {
        if (name == null) {
            return "";
        }
        return name.replace("주식회사", "")
                .replace("유한회사", "")
                .replace("(주)", "")
                .replace("㈜", "")
                .replace("(유)", "")
                .replaceAll("[\\s.]", "")
                .toLowerCase();
    }

    private static boolean isSoloRoomFor(Room room, AgentType type) {
        List<RoomAgent> agents = room.getAgents();
        return agents.size() == 1 && agents.get(0).agentKey().equals(type.key());
    }

    public RoomListResponse list(Long userId, Long coverLetterId) {
        List<Room> rooms = coverLetterId == null
                ? roomRepository.findAllForSidebar(userId)
                : roomRepository.findAllForSidebarByCoverLetter(userId, coverLetterId);

        // lastMessagePreview·running 은 대화 테이블(S15P21A504-130)이 오면 채운다.
        return new RoomListResponse(rooms.stream()
                .map(room -> new RoomListResponse.Room(
                        room.getId(),
                        room.getTitle(),
                        agentCountWithSupervisor(room.getAgents()),
                        null,
                        room.getLastMessageAt(),
                        false))
                .toList());
    }

    public RoomResponse detail(Long userId, Long roomId) {
        Room room = ownedRoom(userId, roomId);
        return toDetail(room, coverLetterOrNull(room.getCoverLetterId()));
    }

    @Transactional
    public RoomResponse update(Long userId, Long roomId, RoomUpdateRequest request) {
        Room room = ownedRoom(userId, roomId);
        if (request.title() != null && !request.title().isBlank()) {
            room.rename(request.title().trim());
        }
        if (request.agents() != null) {
            if (request.agents().isEmpty()) {
                throw new BusinessException(ErrorCode.INVALID_PARAMETER, "에이전트를 최소 1명은 남겨야 합니다.");
            }
            room.replaceAgents(validator.validateAll(request.agents()));
        }
        return toDetail(room, coverLetterOrNull(room.getCoverLetterId()));
    }

    @Transactional
    public void delete(Long userId, Long roomId) {
        roomRepository.delete(ownedRoom(userId, roomId));
    }

    /** 방을 다시 만들지 않고 그 에이전트가 볼 대상만 바꾼다. */
    @Transactional
    public RoomResponse.Agent updateAgentConfig(Long userId, Long roomId, String agentKey,
                                                Map<String, Object> config) {
        Room room = ownedRoom(userId, roomId);
        AgentType type = validator.resolveSelectable(agentKey);

        List<RoomAgent> current = room.getAgents();
        if (current.stream().noneMatch(agent -> agent.agentKey().equals(type.key()))) {
            throw new BusinessException(ErrorCode.AGENT_NOT_IN_ROOM, "이 방에 없는 에이전트입니다: " + agentKey);
        }

        Map<String, Object> validated = validator.validateConfig(type, config);
        List<RoomAgent> replaced = current.stream()
                .map(agent -> agent.agentKey().equals(type.key())
                        ? new RoomAgent(type.key(), validated)
                        : agent)
                .toList();
        room.replaceAgents(replaced);

        return toAgentView(new RoomAgent(type.key(), validated), false, corpNames(replaced));
    }

    private RoomResponse toDetail(Room room, CoverLetter coverLetter) {
        List<RoomAgent> stored = room.getAgents();
        Map<String, String> names = corpNames(stored);

        List<RoomResponse.Agent> agents = new ArrayList<>(stored.stream()
                .map(agent -> toAgentView(agent, false, names))
                .toList());
        if (stored.size() >= 2) {
            agents.add(toAgentView(new RoomAgent(AgentType.SUPERVISOR.key(), Map.of()), true, names));
        }

        return new RoomResponse(
                room.getId(),
                room.getTitle(),
                coverLetter == null
                        ? null
                        : new RoomResponse.CoverLetterRef(coverLetter.getId(), coverLetter.getTitle()),
                jobContextRef(room.getJobContextId()),
                agents,
                room.getCreatedAt(),
                room.getLastMessageAt());
    }

    /**
     * 방에 붙은 공고를 화면 표시용으로 바꾼다.
     *
     * <p>AI 서비스가 분석을 지웠으면 FK 가 job_context_id 를 NULL 로 만든다. 그래도 조회 시점에
     * 사라져 있을 수 있으므로 없으면 공고 없는 방으로 본다 — 방과 대화는 그대로 열려야 한다.
     */
    private RoomResponse.JobContextRef jobContextRef(String contextId) {
        if (contextId == null) {
            return null;
        }
        return jobContextRepository.findById(contextId)
                .map(context -> new RoomResponse.JobContextRef(
                        context.getContextId(), context.getCompanyName(), context.getPositionName()))
                .orElse(null);
    }

    /** 없는 분석을 가리키면 FK 위반이 저장 시점에 터진다. 그 전에 400 으로 돌려준다. */
    private String existingJobContextId(String contextId) {
        if (contextId == null || contextId.isBlank()) {
            return null;
        }
        return jobContextRepository.findById(contextId)
                .map(JobContext::getContextId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_PARAMETER,
                        "채용공고 분석을 찾지 못했습니다."));
    }

    /** 저장된 설정을 화면이 쓰기 좋게 바꾼다. corpCodes 는 기업명·ragReady 를 붙인 companies 가 된다. */
    private RoomResponse.Agent toAgentView(RoomAgent agent, boolean auto, Map<String, String> names) {
        AgentType type = AgentType.from(agent.agentKey())
                .orElseThrow(() -> new BusinessException(ErrorCode.AGENT_NOT_SUPPORTED, agent.agentKey()));

        Map<String, Object> view = new LinkedHashMap<>(agent.config());
        // 필수 설정이 덜 찼으면 아직 쓸 수 없다. 화면이 "설정 필요" 로 보여준다.
        boolean ready = type.isConfigured(agent.config());

        Object corpCodes = view.remove("corpCodes");
        if (corpCodes instanceof Collection<?> codes) {
            List<Map<String, Object>> companies = codes.stream()
                    .map(String::valueOf)
                    .map(code -> {
                        Map<String, Object> one = new LinkedHashMap<String, Object>();
                        one.put("corpCode", code);
                        one.put("name", names.get(code));
                        one.put("ragReady", properties.isRagIndexed(code));
                        return one;
                    })
                    .toList();
            view.put("companies", companies);
            ready = companies.stream().allMatch(one -> Boolean.TRUE.equals(one.get("ragReady")));
        }

        return new RoomResponse.Agent(type.key(), type.displayName(), auto, ready, view);
    }

    /** 설정에 실린 corpCode 를 한 번에 이름으로 바꾼다(에이전트마다 조회하지 않는다). */
    private Map<String, String> corpNames(List<RoomAgent> agents) {
        List<String> codes = agents.stream()
                .map(agent -> agent.config().get("corpCodes"))
                .filter(Collection.class::isInstance)
                .flatMap(value -> ((Collection<?>) value).stream())
                .map(String::valueOf)
                .distinct()
                .toList();
        if (codes.isEmpty()) {
            return Map.of();
        }
        return companyRepository.findAllById(codes).stream()
                .collect(Collectors.toMap(Company::getCorpCode, Company::getCorpName, (first, second) -> first));
    }

    private int agentCountWithSupervisor(List<RoomAgent> agents) {
        return agents.size() >= 2 ? agents.size() + 1 : agents.size();
    }

    private Room ownedRoom(Long userId, Long roomId) {
        return roomRepository.findByIdAndUserId(roomId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ROOM_NOT_FOUND,
                        "검토 방을 찾을 수 없습니다: " + roomId));
    }

    private CoverLetter ownedCoverLetter(Long userId, Long coverLetterId) {
        return coverLetterRepository.findByIdAndUserId(coverLetterId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.COVER_LETTER_NOT_FOUND,
                        "자소서를 찾을 수 없습니다: " + coverLetterId));
    }

    /** 상세를 그릴 때 자소서가 사라졌다면 방만 보여준다(삭제는 CASCADE 라 정상 흐름에선 안 생긴다). */
    private CoverLetter coverLetterOrNull(Long coverLetterId) {
        return coverLetterRepository.findById(coverLetterId).orElse(null);
    }
}
