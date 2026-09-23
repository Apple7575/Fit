package com.ssafy.companyanalysis.agent.ai;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.HttpClientErrorException;

import java.nio.charset.StandardCharsets;
import java.lang.reflect.InvocationTargetException;

import static org.assertj.core.api.Assertions.assertThat;

class AgentAiCallTest {

    @Test
    void translatesAiServer429ToRateLimited() throws Exception {
        var response = HttpClientErrorException.create(
                HttpStatus.TOO_MANY_REQUESTS, "GMS limited", HttpHeaders.EMPTY, new byte[0], StandardCharsets.UTF_8);

        var translate = AgentAiCall.class.getDeclaredMethod(
                "translate", org.springframework.web.client.RestClientResponseException.class, String.class);
        translate.setAccessible(true);
        BusinessException error = invoke(translate, response, "총괄");

        assertThat(error.getErrorCode()).isEqualTo(ErrorCode.AI_RATE_LIMITED);
        assertThat(error.getMessage()).isEqualTo(ErrorCode.AI_RATE_LIMITED.getDefaultMessage());
    }

    private static BusinessException invoke(java.lang.reflect.Method method, Object... arguments) throws Exception {
        try {
            return (BusinessException) method.invoke(null, (Object[]) arguments);
        } catch (InvocationTargetException error) {
            throw (Exception) error.getCause();
        }
    }
}
