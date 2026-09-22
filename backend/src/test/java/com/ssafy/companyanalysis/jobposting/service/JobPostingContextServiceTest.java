package com.ssafy.companyanalysis.jobposting.service;

import com.ssafy.companyanalysis.agent.ai.JobContextClient;
import com.ssafy.companyanalysis.agent.ai.JobSourceClient;
import com.ssafy.companyanalysis.jobposting.cache.JobPostingSourceCache;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingContextResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class JobPostingContextServiceTest {

    private static final String URL = "https://careers.example.com/jobs/123";
    private static final JobContextClient.RegisteredContext REGISTERED =
            new JobContextClient.RegisteredContext("jctx_abc123", "예시기업", "백엔드 개발자", URL);

    private JobContextClient client;
    private JobPostingSourceCache cache;
    private JobPostingContextService service;

    @BeforeEach
    void setUp() {
        client = mock(JobContextClient.class);
        when(client.fromSource(any(), any(), any())).thenReturn(REGISTERED);
        when(client.fromUrl(any(), any(), any())).thenReturn(REGISTERED);
        cache = new JobPostingSourceCache(Duration.ofMinutes(30), 200);
        service = new JobPostingContextService(client, cache);
    }

    private JobSourceClient.JobSource source(String companyName, String positionName) {
        return new JobSourceClient.JobSource("공고 본문입니다.", companyName, positionName, URL,
                "123", "2026-09-01", "2026-09-30", false);
    }

    @Test
    @DisplayName("보관해 둔 본문이 있으면 그것으로 등록해 공고를 다시 긁지 않는다")
    void registersFromCachedSource() {
        String key = cache.put(source("예시기업", "백엔드 개발자"));

        JobPostingContextResponse response =
                service.register(URL, "예시기업", "백엔드 개발자", key);

        assertThat(response.jobContextId()).isEqualTo("jctx_abc123");
        verify(client).fromSource(any(), any(), any());
        verify(client, never()).fromUrl(any(), any(), any());
    }

    @Test
    @DisplayName("사용자가 고친 회사·직무가 공고에서 뽑은 값보다 우선한다")
    void confirmedNamesWinOverExtracted() {
        String key = cache.put(source("사람인", "직무 미상"));

        service.register(URL, "예시기업", "백엔드 개발자", key);

        verify(client).fromSource(any(), eq("예시기업"), eq("백엔드 개발자"));
    }

    @Test
    @DisplayName("보관 키가 없으면 주소로 등록한다")
    void fallsBackToUrlWithoutKey() {
        JobPostingContextResponse response =
                service.register(URL, "예시기업", "백엔드 개발자", null);

        assertThat(response.jobContextId()).isEqualTo("jctx_abc123");
        verify(client).fromUrl(URL, "예시기업", "백엔드 개발자");
        verify(client, never()).fromSource(any(), any(), any());
    }

    @Test
    @DisplayName("보관 시간이 지났으면 주소로 등록한다")
    void fallsBackToUrlWhenExpired() {
        JobPostingSourceCache expired = new JobPostingSourceCache(Duration.ZERO, 200);
        String key = expired.put(source("예시기업", "백엔드 개발자"));

        new JobPostingContextService(client, expired)
                .register(URL, "예시기업", "백엔드 개발자", key);

        verify(client).fromUrl(URL, "예시기업", "백엔드 개발자");
    }

    @Test
    @DisplayName("회사명이나 직무명을 끝내 못 채우면 주소로 등록한다 — AI 가 공고를 다시 읽어 찾는다")
    void fallsBackToUrlWhenNamesMissing() {
        String key = cache.put(source(null, null));

        service.register(URL, null, null, key);

        verify(client).fromUrl(URL, null, null);
        verify(client, never()).fromSource(any(), any(), any());
    }

    @Test
    @DisplayName("리다이렉트 후 주소를 못 받으면 사용자가 준 주소를 돌려준다")
    void fallsBackToRequestedUrl() {
        when(client.fromUrl(any(), any(), any())).thenReturn(
                new JobContextClient.RegisteredContext("jctx_abc123", "예시기업", "백엔드 개발자", null));

        JobPostingContextResponse response =
                service.register(URL, "예시기업", "백엔드 개발자", null);

        assertThat(response.sourceUrl()).isEqualTo(URL);
    }
}
