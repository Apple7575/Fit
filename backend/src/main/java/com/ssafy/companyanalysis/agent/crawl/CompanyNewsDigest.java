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

    private static final int DEFAULT_MONTHS = 6;
    private static final int PER_COMPANY = 10;
    private static final int DAYS_PER_MONTH = 30;

    private final CompanyNewsService companyNewsService;

    public CompanyNewsDigest(CompanyNewsService companyNewsService) {
        this.companyNewsService = companyNewsService;
    }

    /**
     * @param config 에이전트 설정. corpCodes 와 months 를 읽는다
     * @return 회사별 최근 기사 제목 목록. 한 건도 없으면 예외
     */
    public String digest(Map<String, Object> config) {
        List<String> corpCodes = corpCodes(config);
        int days = months(config) * DAYS_PER_MONTH;

        String text = corpCodes.stream()
                .map(corpCode -> section(corpCode, days))
                .filter(section -> !section.isBlank())
                .collect(Collectors.joining("\n\n"));

        if (text.isBlank()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "최근 " + months(config) + "개월 안에 수집된 뉴스가 없습니다.");
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

    private static int months(Map<String, Object> config) {
        Object value = config.get("months");
        if (value instanceof Number number && number.intValue() > 0) {
            return number.intValue();
        }
        return DEFAULT_MONTHS;
    }
}
