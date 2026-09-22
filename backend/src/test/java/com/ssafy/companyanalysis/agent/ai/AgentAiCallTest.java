package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.RETURNS_DEEP_STUBS;
import static org.mockito.Mockito.mock;

class AgentAiCallTest {

    private static RestClient failingClient(int status, String body) {
        RestClient client = mock(RestClient.class, RETURNS_DEEP_STUBS);
        RestClientResponseException error = new RestClientResponseException(
                "err", HttpStatus.valueOf(status), "err", null,
                body.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8);
        given(client.post().uri(anyString()).contentType(any()).body(any(Object.class))
                .retrieve().body(any(Class.class)))
                .willThrow(error);
        return client;
    }

    @Test
    @DisplayName("AI 가 LLM 할당량 코드를 담아 502 를 주면 사용자가 할 일이 담긴 문장으로 바꾼다")
    void quotaCodeBecomesUserMessage() {
        RestClient client = failingClient(502,
                "{\"detail\":{\"code\":\"LLM_QUOTA_EXCEEDED\",\"message\":\"AI 요청 한도에 잠시 걸렸습니다.\"}}");

        assertThatThrownBy(() -> AgentAiCall.post(client, "/x", "{}", "총괄"))
                .isInstanceOf(BusinessException.class)
                .satisfies(e -> {
                    assertThat(((BusinessException) e).getErrorCode()).isEqualTo(ErrorCode.AI_FAILED);
                    assertThat(e.getMessage()).isEqualTo(AgentAiCall.QUOTA_MESSAGE);
                });
    }

    @Test
    @DisplayName("할당량이 아닌 502 는 기존 문구 그대로다")
    void other502KeepsGenericMessage() {
        RestClient client = failingClient(502,
                "{\"detail\":{\"code\":\"SUPERVISOR_FAILED\",\"message\":\"ValueError\"}}");

        assertThatThrownBy(() -> AgentAiCall.post(client, "/x", "{}", "총괄"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("총괄 AI 서버가 응답을 만들지 못했습니다.");
    }
}
