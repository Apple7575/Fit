package com.ssafy.companyanalysis.agent.crawl;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 채용공고 URL 에서 본문을 긁어 온다.
 *
 * <p>사람인은 목록 페이지 HTML 에 상세 요강이 없다. 상세는 {@code view-detail?rec_idx=...} 로
 * 따로 내려오므로 그 주소를 만들어 한 번 더 받는다. 그 밖의 사이트는 준 주소를 그대로 받는다.
 *
 * <p>HTML 파서를 따로 들이지 않고 태그를 벗겨 평문으로 만든다. 받는 쪽이 사람이 아니라 모델이라
 * 문서 구조가 남아 있을 필요가 없다. 정교한 선택이 필요해지면 그때 파서를 붙인다.
 */
@Component
public class JobPostingFetcher {

    private static final Logger log = LoggerFactory.getLogger(JobPostingFetcher.class);

    /** 기본 UA 로는 사람인이 307 로 돌려보낸다. */
    private static final String USER_AGENT =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/140.0 Safari/537.36";

    private static final Duration TIMEOUT = Duration.ofSeconds(10);
    /** 공고 하나가 프롬프트를 다 잡아먹지 않게 자른다. */
    private static final int MAX_CHARS = 8000;

    private static final Pattern SARAMIN_REC_IDX = Pattern.compile("[?&]rec_idx=(\\d+)");
    private static final Pattern OG_DESCRIPTION =
            Pattern.compile("(?i)<meta[^>]*property=\"og:description\"[^>]*content=\"([^\"]*)\"");
    private static final Pattern TITLE = Pattern.compile("(?is)<title>(.*?)</title>");

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(TIMEOUT)
            .followRedirects(HttpClient.Redirect.NORMAL)
            .build();

    public String fetch(String url) {
        if (url == null || url.isBlank()) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE, "채용공고 주소가 없습니다.");
        }

        String page = get(url);
        StringBuilder collected = new StringBuilder();

        // 제목과 요약 메타에는 회사·직무·경력·마감일이 들어 있어 본문만큼 쓸모가 있다.
        find(TITLE, page).ifPresent(title -> collected.append(clean(title)).append('\n'));
        find(OG_DESCRIPTION, page).ifPresent(summary -> collected.append(clean(summary)).append('\n'));

        String body = saraminDetail(url).map(this::get).orElse(page);
        collected.append(toText(body));

        String text = collected.toString().trim();
        if (text.length() < 50) {
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                    "채용공고 본문을 읽지 못했습니다. 공고가 이미지로 올라와 있거나 로그인이 필요한 페이지일 수 있습니다.");
        }
        return text.length() > MAX_CHARS ? text.substring(0, MAX_CHARS) : text;
    }

    /** 사람인 공고면 상세 주소를, 아니면 비어 있는 값을 준다. */
    private static java.util.Optional<String> saraminDetail(String url) {
        if (!url.contains("saramin.co.kr")) {
            return java.util.Optional.empty();
        }
        Matcher matcher = SARAMIN_REC_IDX.matcher(url);
        return matcher.find()
                ? java.util.Optional.of(
                        "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=" + matcher.group(1))
                : java.util.Optional.empty();
    }

    private String get(String url) {
        HttpRequest request;
        try {
            request = HttpRequest.newBuilder(URI.create(url))
                    .header("User-Agent", USER_AGENT)
                    .header("Accept-Language", "ko-KR,ko;q=0.9")
                    .header("Referer", "https://www.saramin.co.kr/")
                    .timeout(TIMEOUT)
                    .GET()
                    .build();
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "채용공고 주소가 올바르지 않습니다.");
        }

        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE,
                        "채용공고 페이지를 열지 못했습니다 (" + response.statusCode() + ").");
            }
            return response.body();
        } catch (IOException e) {
            log.warn("채용공고 조회 실패: url={}, reason={}", url, e.getMessage());
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE, "채용공고 페이지에 연결하지 못했습니다.");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException(ErrorCode.AGENT_SOURCE_UNAVAILABLE, "채용공고 조회가 중단됐습니다.");
        }
    }

    /** 태그를 벗겨 평문으로 만든다. 블록 태그는 줄바꿈으로 바꿔 항목 구분을 남긴다. */
    static String toText(String html) {
        String text = html.replaceAll("(?is)<(script|style|noscript)[^>]*>.*?</\\1>", " ");
        text = text.replaceAll("(?i)<br\\s*/?>", "\n");
        text = text.replaceAll("(?i)</(p|div|li|tr|h[1-6])>", "\n");
        text = text.replaceAll("(?s)<[^>]+>", " ");
        return clean(text);
    }

    private static String clean(String raw) {
        String text = raw.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", "\"")
                .replace("&#39;", "'");
        text = text.replaceAll("[ \\t\\u00a0]+", " ");
        text = text.replaceAll("(?m)^ +| +$", "");
        return text.replaceAll("\\n{2,}", "\n").trim();
    }

    private static java.util.Optional<String> find(Pattern pattern, String text) {
        Matcher matcher = pattern.matcher(text);
        return matcher.find() ? java.util.Optional.of(matcher.group(1)) : java.util.Optional.empty();
    }
}
