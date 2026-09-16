package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.JsonNode;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 채용공고를 AI 서버에 등록하고 검토 방에 붙일 분석 식별자를 받아 온다.
 *
 * <p>들어오는 길이 둘이다. 공고 확인 때 긁어 둔 본문이 남아 있으면 그 본문을 그대로 넘기고
 * ({@code POST /jd/internal/job-contexts}), 남아 있지 않으면 주소만 넘겨 AI 가 다시 읽게 한다
 * ({@code POST /jd/internal/job-contexts/from-url}). 앞이 기본이고 뒤는 보관분이 사라졌을 때의
 * 대비책이다 — 공고를 두 번 긁지 않으려는 것이다(S15P21A504-140).
 *
 * <p>화면이 사용자에게 확인받은 회사명·직무명이 AI 가 공고에서 뽑은 값보다 우선한다.
 * 본문을 넘기는 길에서는 둘 다 반드시 있어야 하고, 주소만 넘기는 길에서는 비면 AI 가 뽑은
 * 값을 쓴다.
 *
 * <p>본문을 넘기는 길에서는 원본 응답 바이트의 해시({@code source_content_sha256})가 AI 에
 * 남지 않는다. 등록 API 가 그 필드를 받지 않기 때문이다. 지금 그 값을 읽는 곳은 없다.
 */
@Component
public class JobContextClient {

    private static final String TEXT_PATH = "/jd/internal/job-contexts";
    private static final String URL_PATH = "/jd/internal/job-contexts/from-url";

    private final RestClient agentAiRestClient;
    private final AgentAiProperties properties;

    public JobContextClient(RestClient agentAiRestClient, AgentAiProperties properties) {
        this.agentAiRestClient = agentAiRestClient;
        this.properties = properties;
    }

    /** 확인 때 긁어 둔 본문으로 등록한다. 회사명·직무명은 호출하는 쪽이 채워서 준다. */
    public RegisteredContext fromSource(JobSourceClient.JobSource source,
                                        String companyName,
                                        String positionName) {
        requireBaseUrl();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("company_name", companyName);
        body.put("position_name", positionName);
        body.put("jd_text", source.jdText());
        putIfPresent(body, "job_posting_id", source.jobPostingId());
        putIfPresent(body, "source_url", source.sourceUrl());
        putIfPresent(body, "published_at", source.publishedAt());
        putIfPresent(body, "valid_until", source.validUntil());
        body.put("retrieved_at", LocalDate.now().toString());

        return register(TEXT_PATH, body);
    }

    /** 보관분이 없을 때. AI 가 주소를 다시 읽어 등록까지 한 번에 한다. */
    public RegisteredContext fromUrl(String url, String companyName, String positionName) {
        if (url == null || url.isBlank()) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "채용공고 주소가 없습니다.");
        }
        requireBaseUrl();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("url", url);
        putIfPresent(body, "company_name", companyName);
        putIfPresent(body, "position_name", positionName);

        return register(URL_PATH, body);
    }

    private RegisteredContext register(String path, Map<String, Object> body) {
        JsonNode response;
        try {
            response = agentAiRestClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientResponseException e) {
            throw translate(e);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE);
        }

        String contextId = response == null ? "" : response.path("context_id").asString("");
        if (contextId.isBlank()) {
            throw new BusinessException(ErrorCode.AI_FAILED, "채용공고 분석 식별자를 받지 못했습니다.");
        }
        return new RegisteredContext(
                contextId,
                nullable(response, "company_name"),
                nullable(response, "position_name"),
                nullable(response, "source_url"));
    }

    private void requireBaseUrl() {
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "채용공고를 등록할 AI 서버 주소가 설정되지 않았습니다.");
        }
    }

    /** AI 쪽이 빈 문자열을 받지 않는다. 없는 값은 아예 빼고 보낸다. */
    private static void putIfPresent(Map<String, Object> body, String field, String value) {
        if (value != null && !value.isBlank()) {
            body.put(field, value);
        }
    }

    /**
     * 502 를 {@link JobSourceClient} 와 다르게 옮긴다. 거기서는 주소를 못 연 것이지만, 등록까지
     * 왔다는 것은 같은 공고를 조금 전에 이미 읽었다는 뜻이다. 남는 경우는 요구사항을 정리하는
     * 모델 쪽 실패라서 사용자에게 주소를 다시 보라고 할 일이 아니다.
     */
    private static BusinessException translate(RestClientResponseException e) {
        return switch (e.getStatusCode().value()) {
            // AI 쪽이 사람이 읽을 한국어 사유를 준다(본문 없음·기업명 확인 실패 등). 그대로 전한다.
            case 415, 422 -> new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED,
                    AgentAiCall.userDetail(e, ErrorCode.JOB_POSTING_PARSE_FAILED.getDefaultMessage()));
            case 503 -> new BusinessException(ErrorCode.AI_UNAVAILABLE);
            default -> new BusinessException(ErrorCode.AI_FAILED);
        };
    }

    private static String nullable(JsonNode response, String field) {
        String value = response.path(field).asString("");
        return value.isBlank() ? null : value;
    }

    /**
     * @param contextId 검토 방에 물려 줄 분석 식별자
     * @param companyName AI 에 저장된 회사명. 화면이 보낸 값이 있으면 그 값이다
     */
    public record RegisteredContext(String contextId, String companyName, String positionName,
                                    String sourceUrl) {
    }
}
