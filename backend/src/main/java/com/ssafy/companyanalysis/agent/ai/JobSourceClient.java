package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.JsonNode;

import java.util.Map;

/**
 * 채용공고 URL 의 본문을 AI 서버에서 받아 온다({@code POST /jd/internal/job-sources/from-url}).
 *
 * <p>백엔드가 사용자가 준 주소로 직접 붙지 않는다. 그렇게 하면 사내망 주소를 넣어 내부 서비스를
 * 찔러 보는 통로가 된다. AI 쪽 수집기는 호스트를 풀어 공인 대역인지 보고 리다이렉트 뒤에도 최종
 * 주소를 다시 검사하며, 응답 크기와 형식까지 제한한다.
 *
 * <p>여기서는 저장하지 않는다. 받은 본문은 회사명·직무를 뽑는 데 쓰고, 사용자가 검토를
 * 시작하면 그대로 등록에 넘기려고 잠시 보관한다(JobPostingSourceCache).
 */
@Component
public class JobSourceClient {

    private final RestClient agentAiRestClient;
    private final AgentAiProperties properties;

    public JobSourceClient(RestClient agentAiRestClient, AgentAiProperties properties) {
        this.agentAiRestClient = agentAiRestClient;
        this.properties = properties;
    }

    public JobSource fromUrl(String url) {
        if (url == null || url.isBlank()) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "채용공고 주소가 없습니다.");
        }
        if (!properties.hasBaseUrl()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "채용공고를 읽을 AI 서버 주소가 설정되지 않았습니다.");
        }

        JsonNode response;
        try {
            response = agentAiRestClient.post()
                    .uri("/jd/internal/job-sources/from-url")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("url", url))
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientResponseException e) {
            throw translate(e);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_UNAVAILABLE);
        }
        if (response == null || response.path("jd_text").asString("").isBlank()) {
            throw new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED);
        }

        return new JobSource(
                response.path("jd_text").asString(""),
                nullable(response, "company_name"),
                nullable(response, "position_name"),
                nullable(response, "source_url"),
                nullable(response, "job_posting_id"),
                nullable(response, "published_at"),
                nullable(response, "valid_until"));
    }

    /**
     * 주소를 열지 못한 것(502)과 열었지만 쓸 수 없는 것(415·422)을 갈라 놓는다. 앞은 공고 페이지
     * 쪽 문제이고 뒤는 사용자가 준 주소 쪽 문제라, 한 문구로 뭉치면 사용자가 자기 오타를 서버
     * 탓으로 본다.
     */
    private static BusinessException translate(RestClientResponseException e) {
        return switch (e.getStatusCode().value()) {
            case 502 -> new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "채용공고 페이지에 연결하지 못했습니다. 주소를 다시 확인해 주세요.");
            // AI 쪽이 사람이 읽을 한국어 사유를 준다(내부망 주소·본문 없음 등). 그대로 전한다.
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
     * @param companyName  AI 가 공고 메타데이터에서 찾은 회사명. 못 찾으면 null
     * @param positionName 같은 자리에서 찾은 직무명. 못 찾으면 null
     * @param sourceUrl    리다이렉트를 따라간 뒤의 최종 주소
     * @param publishedAt  공고 게시일({@code YYYY-MM-DD}). 등록할 때 함께 넘긴다
     */
    public record JobSource(String jdText, String companyName, String positionName, String sourceUrl,
                            String jobPostingId, String publishedAt, String validUntil) {
    }
}
