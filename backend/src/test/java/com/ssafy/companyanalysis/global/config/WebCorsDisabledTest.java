package com.ssafy.companyanalysis.global.config;

import com.ssafy.companyanalysis.company.controller.CompanyController;
import com.ssafy.companyanalysis.company.dto.CompanySearchResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.company.service.CompanySearchService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
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
 * 허용 Origin 을 비워 둔 기본 상태(= 배포 기본값)의 동작.
 *
 * <p>이 상태가 안전한 쪽이어야 한다. 설정을 깜빡 빠뜨렸을 때 아무 Origin 이나 열리는 사고를 막는다.
 */
@WebMvcTest(CompanyController.class)
@TestPropertySource(properties = "app.cors.allowed-origins=")
class WebCorsDisabledTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CompanySearchService companySearchService;

    @MockitoBean
    private CompanyDetailService companyDetailService;

    @MockitoBean
    private CompanyProfileService companyProfileService;

    /**
     * CORS 매핑이 없으면 preflight 는 Spring MVC 의 기본 OPTIONS 처리로 넘어가 200 이 된다.
     * 응답에 Allow-Origin 이 없으므로 브라우저가 본 요청을 막는다 — 허용되지 않는다는 결과는 같다.
     * 여기서 지켜야 할 것은 상태 코드가 아니라 Allow-Origin 이 절대 붙지 않는다는 점이다.
     */
    @Test
    @DisplayName("허용 Origin 이 없으면 preflight 응답에 Allow-Origin 이 붙지 않는다")
    void preflightCarriesNoAllowOriginWhenNoOriginConfigured() throws Exception {
        mockMvc.perform(options("/api/companies")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Methods"));
    }

    @Test
    @DisplayName("CORS 를 끄더라도 같은 오리진 요청은 그대로 처리된다")
    void sameOriginRequestStillWorks() throws Exception {
        given(companySearchService.search(eq("삼성"), anyInt(), anyInt()))
                .willReturn(new CompanySearchResponse(List.of(), 0));

        mockMvc.perform(get("/api/companies").param("keyword", "삼성"))
                .andExpect(status().isOk())
                .andExpect(header().doesNotExist("Access-Control-Allow-Origin"));
    }
}
