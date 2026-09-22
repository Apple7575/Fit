package com.ssafy.companyanalysis.jobposting.service;

import com.ssafy.companyanalysis.agent.ai.AgentLlmClient;
import com.ssafy.companyanalysis.agent.ai.JobSourceClient;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.jobposting.cache.JobPostingSourceCache;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingParseResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class JobPostingParseServiceTest {

    private static final String POSTING = "채용공고 본문";

    private JobPostingParseService service(String modelOutput) {
        return service(modelOutput,
                new JobSourceClient.JobSource(POSTING, null, null, null, null, null, null, false));
    }

    private JobPostingParseService service(String modelOutput, JobSourceClient.JobSource source) {
        JobSourceClient jobSourceClient = mock(JobSourceClient.class);
        when(jobSourceClient.fromUrl(anyString())).thenReturn(source);

        AgentLlmClient llmClient = mock(AgentLlmClient.class);
        when(llmClient.generateJson(any(), any())).thenReturn(modelOutput);

        return new JobPostingParseService(jobSourceClient, llmClient, new ObjectMapper(),
                new JobPostingSourceCache(Duration.ofMinutes(30), 200));
    }

    @Test
    @DisplayName("모델이 JSON 을 안 주면 수집 단계가 찾은 회사·직무로 이어간다")
    void fallsBackWhenModelBreaksFormat() {
        // 모델이 형식을 어기는 일이 드물게 있다. 그때 수집 단계가 이미 찾아 둔 값까지
        // 버리면 화면에는 "찾지 못했습니다" 만 남는다.
        JobPostingParseResponse response = service("사업기획·운영, 조사연구",
                new JobSourceClient.JobSource(POSTING, "금융결제원", "신입직원",
                        "https://example.com/job/8", null, null, null, false))
                .parse("https://example.com/job/8");

        assertThat(response.companyName()).isEqualTo("금융결제원");
        assertThat(response.positions()).containsExactly("신입직원");
    }

    @Test
    @DisplayName("본문을 얻은 공고는 등록에서 재사용하도록 보관 키를 준다")
    void keepsSourceForRegistration() {
        JobPostingParseResponse response = service("""
                {"companyName": "삼성전자", "positions": ["백엔드 개발자"]}
                """).parse("https://example.com/job/1");

        assertThat(response.sourceKey()).isNotNull();
    }

    @Test
    @DisplayName("제목·메타만으로 채운 응답은 보관하지 않는다")
    void doesNotKeepMetadataOnlySource() {
        JobPostingParseResponse response = service("""
                {"companyName": "중앙대학교의료원", "positions": ["기능사"]}
                """, new JobSourceClient.JobSource("[중앙대학교의료원] 기능사 채용", null, null,
                        "https://example.com/job/9", null, null, null, true))
                .parse("https://example.com/job/9");

        assertThat(response.companyName()).isEqualTo("중앙대학교의료원");
        // 보관 키가 없어야 등록 쪽이 주소로 다시 읽는다. 그대로 넘기면 본문이 거의 없는
        // 공고가 검토 방에 붙는다.
        assertThat(response.sourceKey()).isNull();
    }

    @Test
    @DisplayName("공고에서 회사명과 직무를 읽어 낸다")
    void readsCompanyAndPositions() {
        JobPostingParseResponse response = service("""
                {"companyName": "삼성전자", "positions": ["백엔드 개발자", "데이터 엔지니어"]}
                """).parse("https://example.com/job/1");

        assertThat(response.companyName()).isEqualTo("삼성전자");
        assertThat(response.positions()).containsExactly("백엔드 개발자", "데이터 엔지니어");
        assertThat(response.sourceUrl()).isEqualTo("https://example.com/job/1");
    }

    @Test
    @DisplayName("같은 직무가 여러 번 나오면 하나로 합치고 공고에 나온 순서를 지킨다")
    void mergesDuplicatePositionsKeepingOrder() {
        JobPostingParseResponse response = service("""
                {"companyName": "카카오", "positions": ["서버 개발", "웹 프론트엔드", "서버 개발"]}
                """).parse("https://example.com/job/2");

        assertThat(response.positions()).containsExactly("서버 개발", "웹 프론트엔드");
    }

    @Test
    @DisplayName("회사명을 못 찾아도 직무가 있으면 직무만 돌려준다 — 회사는 사용자가 채우면 된다")
    void allowsMissingCompanyWhenPositionsFound() {
        JobPostingParseResponse response = service("""
                {"companyName": null, "positions": ["QA 엔지니어"]}
                """).parse("https://example.com/job/3");

        assertThat(response.companyName()).isNull();
        assertThat(response.positions()).containsExactly("QA 엔지니어");
    }

    @Test
    @DisplayName("모델이 빈 문자열이나 \"null\" 을 보내도 회사명 없음으로 본다")
    void treatsBlankAndLiteralNullAsMissing() {
        JobPostingParseResponse response = service("""
                {"companyName": "null", "positions": ["  ", "PM"]}
                """).parse("https://example.com/job/4");

        assertThat(response.companyName()).isNull();
        assertThat(response.positions()).containsExactly("PM");
    }

    @Test
    @DisplayName("회사도 직무도 못 찾으면 400 을 낸다 — 화면이 빈 값으로 덮어쓰지 않게 한다")
    void failsWhenNothingFound() {
        assertThatThrownBy(() -> service("""
                {"companyName": null, "positions": []}
                """).parse("https://example.com/job/5"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.JOB_POSTING_PARSE_FAILED);
    }

    @Test
    @DisplayName("모델 응답이 JSON 이 아니고 수집 값도 없으면 400 을 낸다")
    void failsWhenModelReturnsNonJson() {
        assertThatThrownBy(() -> service("죄송합니다, 공고를 읽을 수 없습니다.")
                .parse("https://example.com/job/6"))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).getErrorCode())
                .isEqualTo(ErrorCode.JOB_POSTING_PARSE_FAILED);
    }

    @Test
    @DisplayName("모델이 못 찾아도 공고 메타데이터에 회사·직무가 있으면 그걸 쓴다")
    void fallsBackToSourceMetadata() {
        JobPostingParseResponse response = service("""
                {"companyName": null, "positions": []}
                """, new JobSourceClient.JobSource(POSTING, "네이버", "백엔드 개발자",
                        "https://example.com/job/7", null, null, null, false))
                .parse("https://example.com/job/7");

        assertThat(response.companyName()).isEqualTo("네이버");
        assertThat(response.positions()).containsExactly("백엔드 개발자");
    }
}
