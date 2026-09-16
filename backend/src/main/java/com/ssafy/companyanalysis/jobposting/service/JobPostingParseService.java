package com.ssafy.companyanalysis.jobposting.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.JobSourceClient;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

/**
 * 채용공고 URL 에서 회사명과 모집 직무를 읽어 낸다.
 *
 * <p>본문은 AI 서버에서 받아 온다. 백엔드가 사용자가 준 주소로 직접 붙으면 사내망을 찔러 보는
 * 통로가 되기 때문이다(S15P21A504-140).
 *
 * <p>받은 본문은 남기지 않는다. 화면 입력칸을 채우는 것이 전부라서 저장할 이유가 없다.
 * 공고 원문이 필요해지는 것은 JD 담당 에이전트가 공고를 읽게 될 때이고, 저장은 그때 함께 정한다.
 */
@Service
public class JobPostingParseService {

    private static final Logger log = LoggerFactory.getLogger(JobPostingParseService.class);

    /** 한 공고에서 모집 직무가 이보다 많이 나오면 화면에서 고르기 어렵다. */
    private static final int MAX_POSITIONS = 20;

    private static final String INSTRUCTION = """
            너는 채용공고 원문에서 회사명과 모집 직무를 뽑는다.
            아래 형태의 JSON 만 돌려준다.
            {"companyName": "회사명 또는 null", "positions": ["직무명", ...]}

            규칙:
            - companyName 은 채용하는 회사의 이름이다. 공고가 올라온 채용 사이트 이름(사람인,
              잡코리아, 원티드 등)을 회사명으로 쓰지 않는다.
            - positions 는 공고에 쓰인 직무 이름을 그대로 옮긴다. 줄이거나 일반화하지 않는다.
            - 한 공고에서 여러 직무를 모집하면 전부 담는다. 같은 직무가 여러 번 나오면 하나로 합친다.
            - 공고에 없는 회사나 직무를 지어내지 않는다. 찾지 못하면 companyName 은 null,
              positions 는 빈 배열로 둔다.
            """;

    /** 공고 하나가 프롬프트를 다 잡아먹지 않게 자른다. */
    private static final int MAX_POSTING_CHARS = 8000;

    private final JobSourceClient jobSourceClient;
    private final AgentLlmClient llmClient;
    private final ObjectMapper objectMapper;

    public JobPostingParseService(JobSourceClient jobSourceClient, AgentLlmClient llmClient,
                                  ObjectMapper objectMapper) {
        this.jobSourceClient = jobSourceClient;
        this.llmClient = llmClient;
        this.objectMapper = objectMapper;
    }

    public JobPostingParseResponse parse(String url) {
        JobSourceClient.JobSource source = jobSourceClient.fromUrl(url);
        JsonNode parsed = readJson(llmClient.generateJson(INSTRUCTION, truncate(source.jdText())));

        String companyName = text(parsed.path("companyName"));
        List<String> positions = positions(parsed.path("positions"));

        // 모델이 못 찾아도 공고 메타데이터에 적혀 있을 때가 있다. 빈손으로 돌려보내기 전에 쓴다.
        if (companyName == null) {
            companyName = source.companyName();
        }
        if (positions.isEmpty() && source.positionName() != null) {
            positions = List.of(source.positionName());
        }

        if (companyName == null && positions.isEmpty()) {
            throw new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED);
        }
        return new JobPostingParseResponse(companyName, positions, url);
    }

    private static String truncate(String posting) {
        return posting.length() > MAX_POSTING_CHARS ? posting.substring(0, MAX_POSTING_CHARS) : posting;
    }

    private JsonNode readJson(String raw) {
        try {
            return objectMapper.readTree(raw);
        } catch (JacksonException e) {
            log.warn("공고 파싱 응답이 JSON 이 아님: reason={}", e.getMessage());
            throw new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED);
        }
    }

    /** 중복은 합치고 순서는 공고에 나온 대로 둔다. */
    private static List<String> positions(JsonNode node) {
        if (!node.isArray()) {
            return List.of();
        }
        LinkedHashSet<String> unique = new LinkedHashSet<>();
        for (JsonNode element : node) {
            String value = text(element);
            if (value != null) {
                unique.add(value);
            }
            if (unique.size() >= MAX_POSITIONS) {
                break;
            }
        }
        return new ArrayList<>(unique);
    }

    /** 모델이 문자열 "null" 이나 빈 칸을 보내는 일이 있어 같이 걸러 낸다. */
    private static String text(JsonNode node) {
        if (node == null || !node.isString()) {
            return null;
        }
        String value = node.stringValue().trim();
        return value.isEmpty() || "null".equalsIgnoreCase(value) ? null : value;
    }
}
