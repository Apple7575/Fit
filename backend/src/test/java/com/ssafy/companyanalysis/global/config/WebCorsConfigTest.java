package com.ssafy.companyanalysis.global.config;

import com.ssafy.companyanalysis.company.controller.CompanyController;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 허용 Origin 이 설정된 상태의 CORS 동작.
 *
 * <p>실제 엔드포인트(/api/companies)로 확인한다. 테스트 전용 컨트롤러를 두면 매핑 경로가
 * 어긋나도 통과해 버려서, 정작 막아야 할 실수를 못 잡는다.
 */
@WebMvcTest(CompanyController.class)
@AutoConfigureMockMvc(addFilters = false)
@TestPropertySource(properties = {
        "app.cors.allowed-origins=http://localhost:5173,http://127.0.0.1:5173",
        "app.cors.max-age=30m"
})
class WebCorsConfigTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySearchService companySearchService;

    @MockitoBean
    private CompanyDetailService companyDetailService;

    @MockitoBean
    private CompanyProfileService companyProfileService;

    @Test
    @DisplayName("허용 목록에 있는 Origin 의 preflight 는 통과하고 허용 메서드·캐시 시간을 알려준다")
    void preflightFromAllowedOriginSucceeds() throws Exception {
        mockMvc.perform(options("/api/companies")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"))
                .andExpect(header().stringValues("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS,POST,PUT,PATCH,DELETE"))
                .andExpect(header().string("Access-Control-Max-Age", "1800"));
    }

    @Test
    @DisplayName("허용 목록의 두 번째 Origin 도 그대로 반사된다")
    void preflightFromSecondAllowedOriginSucceeds() throws Exception {
        mockMvc.perform(options("/api/companies")
                        .header("Origin", "http://127.0.0.1:5173")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://127.0.0.1:5173"));
    }

    @Test
    @DisplayName("허용 목록에 없는 Origin 의 preflight 는 거부된다")
    void preflightFromUnknownOriginIsRejected() throws Exception {
        mockMvc.perform(options("/api/companies")
                        .header("Origin", "https://evil.example.com")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isForbidden())
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
    }

    @Test
    @DisplayName("포트가 다르면 다른 Origin 이므로 거부된다")
    void preflightFromDifferentPortIsRejected() throws Exception {
        mockMvc.perform(options("/api/companies")
                        .header("Origin", "http://localhost:3000")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("본 요청 응답에 Allow-Origin 이 붙고, 세션 쿠키를 위해 인증정보 허용도 켜진다")
    void actualRequestCarriesAllowOriginHeader() throws Exception {
        given(companySearchService.search(eq("삼성"), anyInt(), anyInt()))
                .willReturn(new CompanySearchResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies")
                        .param("keyword", "삼성")
                        .header("Origin", "http://localhost:5173"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"))
                .andExpect(header().string("Access-Control-Allow-Credentials", "true"));
    }
}
