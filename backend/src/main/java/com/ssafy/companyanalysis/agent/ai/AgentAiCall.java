package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import tools.jackson.databind.JsonNode;

/**
 * 포지션·글쓰기 API 의 공통 호출과 오류 변환.
 *
 * <p>상태코드의 뜻은 AI 쪽이 정해 놓았다 — 422 는 우리가 보낸 요청이 틀린 것, 502 는 모델
 * 호출·검증 실패, 503 은 모델 접속 설정이 없는 것이다. 셋을 같은 문구로 뭉뚱그리면 우리
 * 잘못인지 저쪽 문제인지 화면만 보고는 갈라낼 수 없다.
 */
final class AgentAiCall {

    private static final int DETAIL_LIMIT = 120;
    private static final int USER_DETAIL_LIMIT = 200;

    private AgentAiCall() {
    }

    static JsonNode post(RestClient client, String path, Object body, String agentName) {
        JsonNode response;
        try {
            response = client.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientResponseException e) {
            throw translate(e, agentName);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_FAILED,
                    agentName + " AI 서버에 연결하지 못했습니다.");
        }
        if (response == null) {
            throw new BusinessException(ErrorCode.AI_FAILED, agentName + " 응답이 비어 있습니다.");
        }
        return response;
    }

    static JsonNode get(RestClient client, String path, String agentName) {
        JsonNode response;
        try {
            response = client.get()
                    .uri(path)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (RestClientResponseException e) {
            throw translate(e, agentName);
        } catch (RestClientException e) {
            throw new BusinessException(ErrorCode.AI_FAILED,
                    agentName + " AI 서버에 연결하지 못했습니다.");
        }
        if (response == null) {
            throw new BusinessException(ErrorCode.AI_FAILED, agentName + " 응답이 비어 있습니다.");
        }
        return response;
    }

    /** AI 쪽이 LLM 할당량(429)에 막혔을 때 502 본문에 넣는 코드. ai/llm/contracts.py 와 같은 값이다. */
    static final String QUOTA_CODE = "LLM_QUOTA_EXCEEDED";
    /** 화면에 그대로 뜨는 문장. 사용자가 할 일(잠시 뒤 재시도)이 담겨야 한다. */
    static final String QUOTA_MESSAGE = "AI 요청 한도에 잠시 걸렸습니다. 1분쯤 뒤에 다시 시도해 주세요.";

    private static BusinessException translate(RestClientResponseException e, String agentName) {
        int status = e.getStatusCode().value();
        if (status == 502 && isQuotaExceeded(e)) {
            // 담당 잘못이 아니라 한도 문제다. "응답을 만들지 못했습니다" 로 뭉뚱그리면 사용자가 자소서를 의심한다.
            return new BusinessException(ErrorCode.AI_FAILED, QUOTA_MESSAGE);
        }
        return switch (status) {
            case 503 -> new BusinessException(ErrorCode.AI_UNAVAILABLE,
                    agentName + " AI 서버가 아직 모델에 연결되지 않았습니다.");
            case 502 -> new BusinessException(ErrorCode.AI_FAILED,
                    agentName + " AI 서버가 응답을 만들지 못했습니다.");
            // 422 는 우리가 보낸 요청이 계약과 어긋났다는 뜻이다. 사유를 남겨야 고칠 수 있다.
            case 422 -> new BusinessException(ErrorCode.AI_FAILED,
                    agentName + " 요청을 AI 서버가 받지 않았습니다: " + detail(e));
            default -> new BusinessException(ErrorCode.AI_FAILED,
                    agentName + " AI 호출이 " + status + " 로 실패했습니다.");
        };
    }

    /**
     * FastAPI 가 {@code {"detail": ...}} 로 주는 사유만 뽑는다. 화면에 그대로 띄우는 문구라
     * 본문 전체를 옮기지 않는다.
     */
    static String userDetail(RestClientResponseException e, String fallback) {
        String body = e.getResponseBodyAsString();
        if (body == null || body.isBlank()) {
            return fallback;
        }
        int key = body.indexOf("\"detail\"");
        if (key < 0) {
            return fallback;
        }
        int open = body.indexOf('"', body.indexOf(':', key) + 1);
        int close = open < 0 ? -1 : body.indexOf('"', open + 1);
        if (open < 0 || close < 0) {
            return fallback;
        }
        String message = body.substring(open + 1, close).trim();
        if (message.isEmpty()) {
            return fallback;
        }
        return message.length() > USER_DETAIL_LIMIT ? message.substring(0, USER_DETAIL_LIMIT) : message;
    }

    private static boolean isQuotaExceeded(RestClientResponseException e) {
        String body = e.getResponseBodyAsString();
        return body != null && body.contains("\"" + QUOTA_CODE + "\"");
    }

    private static String detail(RestClientResponseException e) {
        String body = e.getResponseBodyAsString();
        if (body == null || body.isBlank()) {
            return "사유 없음";
        }
        String oneLine = body.replaceAll("\s+", " ").trim();
        return oneLine.length() > DETAIL_LIMIT ? oneLine.substring(0, DETAIL_LIMIT) : oneLine;
    }
}
