package com.ssafy.companyanalysis.agent.crawl;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import com.ssafy.companyanalysis.news.dto.CompanyNewsResponse;
import com.ssafy.companyanalysis.news.service.CompanyNewsService;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 뉴스/트렌드 담당이 볼 기사 목록을 만든다.
 *
 * <p>새로 수집하지 않는다. 기업분석 기능이 이미 쌓아 둔 {@code news_article} 을 그대로 읽는다.
 */
@Component
public class CompanyNewsDigest {

    /**
     * 얼마나 거슬러 올라가 볼지. 사용자가 고르게 하지 않는다 — 자소서에 얹을 이슈를 찾는 것이
     * 목적이라 기간을 좁힐 이유가 없고, 늘려 봐야 오래된 기사가 딸려 와 도움이 안 된다.
     */
    private static final int MONTHS = 6;
    private static final int PER_COMPANY = 10;
    private static final int DAYS = MONTHS * 30;

    private final CompanyNewsService companyNewsService;

    public CompanyNewsDigest(CompanyNewsService companyNewsService) {
        this.companyNewsService = companyNewsService;
    }

    /**
     * @param config 에이전트 설정. corpCodes 를 읽는다
     * @return 회사별 최근 기사 제목 목록. 한 건도 없으면 예외
     */
    public String digest(Map<String, Object> config) {
        String text = corpCodes(config).stream()
                .map(corpCode -> section(corpCode, DAYS))
                .filter(section -> !section.isBlank())
                .collect(Collectors.joining("\n\n"));

        if (text.isBlank()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "최근 " + MONTHS + "개월 안에 수집된 뉴스가 없습니다.");
        }
        return text;
    }

    private String section(String corpCode, int days) {
        // 중요도가 없는 기사도 버리지 않는다. 로컬·초기 데이터에는 AI 분석이 안 돌아 있다.
        CompanyNewsResponse news = companyNewsService.getNews(corpCode, days, "latest", 1, PER_COMPANY);
        if (news.items().isEmpty()) {
            return "";
        }
        String lines = news.items().stream()
                .map(item -> "- [" + item.publishedAt() + "] " + item.title())
                .collect(Collectors.joining("\n"));
        return "[" + corpCode + " 최근 기사 " + news.total() + "건 중 " + news.items().size() + "건]\n" + lines;
    }

    private static List<String> corpCodes(Map<String, Object> config) {
        Object value = config.get("corpCodes");
        if (!(value instanceof Collection<?> raw) || raw.isEmpty()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE, "볼 기업이 지정되지 않았습니다.");
        }
        return raw.stream().map(String::valueOf).toList();
    }
}
