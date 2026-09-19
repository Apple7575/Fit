package com.ssafy.companyanalysis.auth.service;

import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.io.UnsupportedEncodingException;
import java.nio.charset.StandardCharsets;

@Component
public class VerificationMailSender {

    private static final Logger log = LoggerFactory.getLogger(VerificationMailSender.class);

    private static final String SUBJECT = "[Fit] 이메일 인증";
    private static final String FROM_NAME = "Fit";
    private static final String TEMPLATE_PATH = "mail/verify-email.html";
    private static final String LINK_PLACEHOLDER = "{{VERIFY_URL}}";

    // 본문 이미지는 프론트가 서빙하는 절대 URL 로 참조한다.
    // (CID 인라인은 Gmail 웹에서 자주 깨져, 호스팅 이미지가 가장 호환성이 좋다.)
    private static final String LOGO_PLACEHOLDER = "{{LOGO_URL}}";
    private static final String CHICK_PLACEHOLDER = "{{CHICK_URL}}";
    private static final String LOGO_PATH = "/mail/logo.png";
    private static final String CHICK_PATH = "/mail/chick.png";

    /** HTML 을 못 읽는 클라이언트를 위한 대체 본문(multipart/alternative). */
    private static final String PLAIN_TEXT = """
            Fit 이메일 인증

            Fit 에 가입해 주셔서 반갑습니다.
            아래 링크를 열어 이메일 주소를 인증해 주세요. 링크는 24시간 동안 유효합니다.

            %s

            직접 가입하신 적이 없다면 이 메일은 무시하셔도 됩니다.
            """;

    private final ObjectProvider<JavaMailSender> mailSender;
    private final String mailHost;
    private final String from;
    private final String frontendBaseUrl;
    private final String htmlTemplate;

    public VerificationMailSender(ObjectProvider<JavaMailSender> mailSender,
            @Value("${spring.mail.host:}") String mailHost,
            @Value("${app.mail.from}") String from,
            @Value("${app.frontend-base-url}") String frontendBaseUrl) {
        this.mailSender = mailSender;
        this.mailHost = mailHost;
        this.from = from;
        this.frontendBaseUrl = frontendBaseUrl;
        this.htmlTemplate = loadTemplate();
    }

    @Async
    public void send(String toEmail, String rawToken) {
        String link = frontendBaseUrl + "/verify?token=" + rawToken;

        // SMTP host 가 없으면(로컬 등) 발송하지 않고 링크를 로그로만 남긴다.
        JavaMailSender sender = mailSender.getIfAvailable();
        if (sender == null || mailHost.isBlank()) {
            log.warn("메일 발송기가 없어 인증 링크를 로그로 남긴다. to={} link={}", toEmail, link);
            return;
        }

        String html = htmlTemplate
                .replace(LINK_PLACEHOLDER, link)
                .replace(LOGO_PLACEHOLDER, frontendBaseUrl + LOGO_PATH)
                .replace(CHICK_PLACEHOLDER, frontendBaseUrl + CHICK_PATH);
        String text = PLAIN_TEXT.formatted(link);

        try {
            MimeMessage message = sender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, StandardCharsets.UTF_8.name());
            helper.setFrom(from, FROM_NAME);
            helper.setTo(toEmail);
            helper.setSubject(SUBJECT);
            helper.setText(text, html); // (plain, html) → multipart/alternative
            sender.send(message);
        } catch (MessagingException | UnsupportedEncodingException e) {
            log.error("인증 메일 발송에 실패했다. to={}", toEmail, e);
        }
    }

    private String loadTemplate() {
        try {
            return new ClassPathResource(TEMPLATE_PATH).getContentAsString(StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("인증 메일 템플릿을 읽지 못했다: " + TEMPLATE_PATH, e);
        }
    }
}
