package com.ssafy.companyanalysis.jobposting.service;

import com.ssafy.companyanalysis.agent.ai.JobContextClient;
import com.ssafy.companyanalysis.agent.ai.JobSourceClient;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.jobposting.cache.JobPostingSourceCache;
import com.ssafy.companyanalysis.jobposting.dto.JobPostingContextResponse;
import org.springframework.stereotype.Service;

import java.util.Optional;

/**
 * 채용공고를 AI 서버에 등록하고 검토 방에 붙일 식별자를 돌려준다.
 *
 * <p>백엔드는 공고 본문을 저장하지 않는다. 본문과 요구사항은 AI 쪽 저장소가 들고 있고,
 * 백엔드가 남기는 것은 방에 적어 두는 식별자 하나다(S15P21A504-140).
 *
 * <p>공고 확인 때 긁어 둔 본문이 남아 있으면 그것으로 등록해 공고를 다시 긁지 않는다.
 * 보관 시간이 지났거나 서버가 다시 떴으면 주소로 등록한다 — 사용자에게는 같은 결과다.
 *
 * <p>{@code /api/job-postings/parse} 와 달리 모델이 공고를 요구사항 단위로 정리하므로
 * 호출이 무겁다. 사용자가 회사·직무를 확인한 뒤 한 번만 부른다.
 */
@Service
public class JobPostingContextService {

    private final JobContextClient jobContextClient;
    private final JobPostingSourceCache sourceCache;

    public JobPostingContextService(JobContextClient jobContextClient,
                                    JobPostingSourceCache sourceCache) {
        this.jobContextClient = jobContextClient;
        this.sourceCache = sourceCache;
    }

    public JobPostingContextResponse register(String url, String companyName, String positionName,
                                              String sourceKey) {
        JobContextClient.RegisteredContext context =
                register(url, companyName, positionName, sourceCache.find(sourceKey));
        return new JobPostingContextResponse(
                context.contextId(),
                context.companyName(),
                context.positionName(),
                context.sourceUrl() != null ? context.sourceUrl() : url);
    }

    /**
     * 본문을 넘기는 쪽은 회사명·직무명이 둘 다 있어야 한다. 화면이 확인한 값이 없고 공고에서도
     * 못 뽑았다면 보관분이 있어도 주소로 보낸다 — 그쪽은 AI 가 공고를 다시 읽어 이름을 찾는다.
     */
    private JobContextClient.RegisteredContext register(String url, String companyName,
                                                        String positionName,
                                                        Optional<JobSourceClient.JobSource> cached) {
        if (cached.isPresent()) {
            JobSourceClient.JobSource source = cached.get();
            String company = firstPresent(companyName, source.companyName());
            String position = firstPresent(positionName, source.positionName());
            if (company != null && position != null) {
                return jobContextClient.fromSource(source, company, position);
            }
        }
        // 붙여넣은 이미지로 확인한 공고에는 주소가 없다. 보관분이 사라졌으면(30분 만료·재기동)
        // 다시 읽을 곳이 없으므로, 주소로 되돌아가는 대신 사용자에게 다시 넣어 달라고 한다.
        if (url == null || url.isBlank()) {
            throw new BusinessException(ErrorCode.JOB_POSTING_PARSE_FAILED,
                    "공고 내용을 다시 넣어 주세요.");
        }
        return jobContextClient.fromUrl(url, companyName, positionName);
    }

    private static String firstPresent(String confirmed, String extracted) {
        if (confirmed != null && !confirmed.isBlank()) {
            return confirmed;
        }
        return extracted != null && !extracted.isBlank() ? extracted : null;
    }
}
