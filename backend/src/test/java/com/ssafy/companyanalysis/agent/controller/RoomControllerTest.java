package com.ssafy.companyanalysis.agent.controller;

import com.ssafy.companyanalysis.agent.dto.RoomListResponse;
import com.ssafy.companyanalysis.agent.dto.RoomResponse;
import com.ssafy.companyanalysis.agent.service.RoomService;
import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.global.security.RestAccessDeniedHandler;
import com.ssafy.companyanalysis.global.security.RestAuthenticationEntryPoint;
import com.ssafy.companyanalysis.global.security.SecurityConfig;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import tools.jackson.databind.ObjectMapper;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(RoomController.class)
@Import({SecurityConfig.class, RestAuthenticationEntryPoint.class, RestAccessDeniedHandler.class})
class RoomControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private RoomService roomService;

    /** 컨트롤러가 principal.getId() 를 읽으므로 인증 주체를 실어 준다. */
    private static UserPrincipal principal() {
        return new UserPrincipal(User.create("me@example.com", "hash", "성경"));
    }

    private static RoomResponse room() {
        return new RoomResponse(31L, "네이버 백엔드 합동 검토",
                new RoomResponse.CoverLetterRef(12L, "2026 상반기 네이버 지원"),
                List.of(new RoomResponse.Agent("company", "기업 RAG 담당", false, true,
                                Map.of("companies", List.of(Map.of("corpCode", "00126380",
                                        "name", "네이버", "ragReady", true)))),
                        new RoomResponse.Agent("supervisor", "총괄", true, true, Map.of())),
                OffsetDateTime.parse("2026-09-13T10:22:00+09:00"), null);
    }

    @Test
    @DisplayName("방 생성은 201 과 표준 응답 봉투로 나간다")
    void createReturnsCreated() throws Exception {
        given(roomService.create(any(), any())).willReturn(room());

        String body = objectMapper.writeValueAsString(Map.of(
                "coverLetterId", 12,
                "title", "네이버 백엔드 합동 검토",
                "agents", List.of(Map.of("agentKey", "company",
                        "config", Map.of("corpCodes", List.of("00126380"))))));

        mockMvc.perform(post("/api/rooms").with(user(principal())).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.roomId").value(31))
                .andExpect(jsonPath("$.data.agents", hasSize(2)))
                .andExpect(jsonPath("$.data.agents[0].config.companies[0].name").value("네이버"))
                .andExpect(jsonPath("$.data.agents[1].auto").value(true))
                .andExpect(jsonPath("$.error").doesNotExist());
    }

    @Test
    @DisplayName("필수 항목이 빠진 생성 요청은 400 INVALID_PARAMETER")
    void createWithoutRequiredFieldIsBadRequest() throws Exception {
        String body = objectMapper.writeValueAsString(Map.of("title", "제목만 있음"));

        mockMvc.perform(post("/api/rooms").with(user(principal())).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_PARAMETER"));
    }

    @Test
    @DisplayName("목록은 coverLetterId 를 그대로 서비스에 넘긴다")
    void listPassesCoverLetterFilter() throws Exception {
        given(roomService.list(any(), eq(12L))).willReturn(new RoomListResponse(
                List.of(new RoomListResponse.Room(31L, "합동 검토", 3, null, null, false))));

        mockMvc.perform(get("/api/rooms").with(user(principal())).param("coverLetterId", "12"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.rooms", hasSize(1)))
                .andExpect(jsonPath("$.data.rooms[0].agentCount").value(3))
                .andExpect(jsonPath("$.data.rooms[0].lastMessagePreview").doesNotExist())
                .andExpect(jsonPath("$.data.rooms[0].running").value(false));
    }

    @Test
    @DisplayName("없는 방은 404 ROOM_NOT_FOUND")
    void unknownRoomIsNotFound() throws Exception {
        given(roomService.detail(any(), eq(999L)))
                .willThrow(new BusinessException(ErrorCode.ROOM_NOT_FOUND, "검토 방을 찾을 수 없습니다: 999"));

        mockMvc.perform(get("/api/rooms/{roomId}", 999).with(user(principal())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("ROOM_NOT_FOUND"));
    }

    @Test
    @DisplayName("삭제는 204 이고 본문이 없다")
    void deleteReturnsNoContent() throws Exception {
        mockMvc.perform(delete("/api/rooms/{roomId}", 31).with(user(principal())).with(csrf()))
                .andExpect(status().isNoContent());

        then(roomService).should().delete(any(), eq(31L));
    }

    @Test
    @DisplayName("에이전트 설정 변경은 그 에이전트 하나만 돌려준다")
    void updateAgentConfigReturnsSingleAgent() throws Exception {
        given(roomService.updateAgentConfig(any(), anyLong(), eq("position"), any()))
                .willReturn(new RoomResponse.Agent("position", "포지션 담당", false, true,
                        Map.of("jobRole", "backend")));

        String body = objectMapper.writeValueAsString(Map.of("config", Map.of("jobRole", "backend")));

        mockMvc.perform(patch("/api/rooms/{roomId}/agents/{agentKey}", 31, "position").with(user(principal())).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.agentKey").value("position"))
                .andExpect(jsonPath("$.data.ready").value(true))
                .andExpect(jsonPath("$.data.config.jobRole").value("backend"));
    }

    @Test
    @DisplayName("인덱싱되지 않은 기업을 고르면 400 COMPANY_RAG_NOT_INDEXED")
    void unindexedCompanyIsBadRequest() throws Exception {
        willThrow(new BusinessException(ErrorCode.COMPANY_RAG_NOT_INDEXED, "분석 자료가 아직 준비되지 않았습니다"))
                .given(roomService).updateAgentConfig(any(), anyLong(), eq("company"), any());

        String body = objectMapper.writeValueAsString(
                Map.of("config", Map.of("corpCodes", List.of("00999999"))));

        mockMvc.perform(patch("/api/rooms/{roomId}/agents/{agentKey}", 31, "company").with(user(principal())).with(csrf())
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("COMPANY_RAG_NOT_INDEXED"));
    }
}
