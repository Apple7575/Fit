package com.ssafy.companyanalysis.jobposting.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.crawl.JobPostingFetcher;
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
 * <p>긁은 본문은 남기지 않는다. 화면 입력칸을 채우는 것이 전부라서 저장할 이유가 없다.
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

    private final JobPostingFetcher fetcher;
    private final AgentLlmClient llmClient;
    private final ObjectMapper objectMapper;

    public JobPostingParseService(JobPostingFetcher fetcher, AgentLlmClient llmClient, ObjectMapper objectMapper) {
        this.fetcher = fetcher;
        this.llmClient = llmClient;
        this.objectMapper = objectMapper;
    }

    public JobPostingParseResponse parse(String url) {
        String posting = fetcher.fetch(url);
        JsonNode parsed = readJson(llmClient.generateJson(INSTRUCTION, posting));

        String companyName = text(parsed.path("companyName"));
        List<String> positions = positions(parsed.path("positions"));

        if (companyName == null && positions.isEmpty()) {
            throw new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED);
        }
        return new JobPostingParseResponse(companyName, positions, url);
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
