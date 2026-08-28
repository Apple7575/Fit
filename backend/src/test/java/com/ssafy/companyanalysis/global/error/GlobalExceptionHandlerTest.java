package com.ssafy.companyanalysis.global.error;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GlobalExceptionHandlerTest {

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new TestController())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    @DisplayName("성공 응답은 success·data 만 담고 error 키는 나가지 않는다")
    void successEnvelope() throws Exception {
        mockMvc.perform(get("/test/ok"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.corpCode").value("00164779"))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("BusinessException 은 ErrorCode 의 상태코드와 코드명으로 변환된다")
    void businessException() throws Exception {
        mockMvc.perform(get("/test/not-found"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("COMPANY_NOT_FOUND"))
                .andExpect(jsonPath("$.error.message").value("해당 기업을 찾을 수 없습니다."))
                .andExpect(jsonPath("$.data").doesNotExist());
    }

    @Test
    @DisplayName("지원하지 않는 지표는 400 METRIC_NOT_SUPPORTED 로 나간다")
    void metricNotSupported() throws Exception {
        mockMvc.perform(get("/test/bad-metric"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("METRIC_NOT_SUPPORTED"));
    }

    @Test
    @DisplayName("필수 파라미터가 없으면 400 INVALID_PARAMETER 로 나간다")
    void missingParameter() throws Exception {
        mockMvc.perform(get("/test/search"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("파라미터 타입이 맞지 않으면 400 INVALID_PARAMETER 로 나간다")
    void typeMismatch() throws Exception {
        mockMvc.perform(get("/test/year").param("year", "이천이십오"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("예상치 못한 예외는 500 으로 바뀌고 내부 정보가 응답에 실리지 않는다")
    void unexpectedExceptionHidesInternals() throws Exception {
        String body = mockMvc.perform(get("/test/boom"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("$.error.message").value("서버 오류가 발생했습니다."))
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andReturn()
                .getResponse()
                .getContentAsString();

        if (body.contains("jdbc:postgresql") || body.contains("com.ssafy")) {
            throw new AssertionError("응답에 내부 정보가 노출되었다: " + body);
        }
    }

    @RestController
    static class TestController {

        @GetMapping("/test/ok")
        ApiResponse<Map<String, String>> ok() {
            return ApiResponse.ok(Map.of("corpCode", "00164779"));
        }

        @GetMapping("/test/not-found")
        ApiResponse<Void> notFound() {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }

        @GetMapping("/test/bad-metric")
        ApiResponse<Void> badMetric() {
            throw new BusinessException(ErrorCode.METRIC_NOT_SUPPORTED);
        }

        @GetMapping("/test/search")
        ApiResponse<Void> search(@RequestParam String keyword) {
            return ApiResponse.ok(null);
        }

        @GetMapping("/test/year")
        ApiResponse<Void> year(@RequestParam int year) {
            return ApiResponse.ok(null);
        }

        @GetMapping("/test/boom")
        ApiResponse<Void> boom() {
            throw new IllegalStateException("jdbc:postgresql://internal-host:5432 접속 실패");
        }
    }
}
