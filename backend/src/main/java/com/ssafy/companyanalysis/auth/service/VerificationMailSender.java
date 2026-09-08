package com.ssafy.companyanalysis.auth.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

@Component
public class VerificationMailSender {

    private static final Logger log = LoggerFactory.getLogger(VerificationMailSender.class);

    private final ObjectProvider<JavaMailSender> mailSender;
    private final String mailHost;
    private final String from;
    private final String frontendBaseUrl;

    public VerificationMailSender(ObjectProvider<JavaMailSender> mailSender,
            @Value("${spring.mail.host:}") String mailHost,
            @Value("${app.mail.from}") String from,
            @Value("${app.frontend-base-url}") String frontendBaseUrl) {
        this.mailSender = mailSender;
        this.mailHost = mailHost;
        this.from = from;
        this.frontendBaseUrl = frontendBaseUrl;
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

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(from);
        message.setTo(toEmail);
        message.setSubject("[기분] 이메일 인증");
        message.setText("아래 링크를 눌러 이메일 인증을 완료하세요. 링크는 24시간 동안 유효합니다.\n\n" + link);
        sender.send(message);
    }
}
