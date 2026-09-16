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

    private static BusinessException translate(RestClientResponseException e, String agentName) {
        int status = e.getStatusCode().value();
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

    private static String detail(RestClientResponseException e) {
        String body = e.getResponseBodyAsString();
        if (body == null || body.isBlank()) {
            return "사유 없음";
        }
        String oneLine = body.replaceAll("\s+", " ").trim();
        return oneLine.length() > DETAIL_LIMIT ? oneLine.substring(0, DETAIL_LIMIT) : oneLine;
    }
}
