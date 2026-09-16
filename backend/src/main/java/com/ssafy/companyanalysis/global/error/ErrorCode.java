package com.ssafy.companyanalysis.global.error;

import org.springframework.http.HttpStatus;

/**
 * 응답의 {@code error.code} 로 나가는 값.
 *
 * <p>INVALID_PARAMETER · METRIC_NOT_SUPPORTED · COMPANY_NOT_FOUND 는 명세에 정의된 코드다.
 * INTERNAL_ERROR 는 명세가 5xx의 존재만 언급하고 코드를 정하지 않아 여기서 신설했다.
 * EMAIL_ALREADY_EXISTS · INVALID_CREDENTIALS · UNAUTHENTICATED · ACCESS_DENIED 는 인증 도입으로 신설했다.
 * ROOM_* · AGENT_* · TURN_IN_PROGRESS 는 자소서 멀티에이전트(S15P21A504-127)에서 신설했다.
 * JOB_POSTING_* 은 공고 URL 확인(S15P21A504-138)에서 신설했다.
 * AI_UNAVAILABLE · AI_FAILED 는 자소서 피드백 전용이던 AI_FEEDBACK_* 을 고친 것이다 —
 * 피드백이 사라진 뒤 에이전트와 공고 확인이 함께 쓴다.
 */
public enum ErrorCode {

    INVALID_PARAMETER(HttpStatus.BAD_REQUEST, "요청 파라미터가 올바르지 않습니다."),
    METRIC_NOT_SUPPORTED(HttpStatus.BAD_REQUEST, "지원하지 않는 지표입니다."),
    COMPANY_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 기업을 찾을 수 없습니다."),
    EMAIL_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 가입된 이메일입니다."),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."),
    UNAUTHENTICATED(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다."),
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "권한이 없습니다."),
    EMAIL_NOT_VERIFIED(HttpStatus.FORBIDDEN, "이메일 인증이 필요합니다."),
    VERIFICATION_TOKEN_INVALID(HttpStatus.BAD_REQUEST, "인증 링크가 유효하지 않거나 만료되었습니다."),
    COVER_LETTER_NOT_FOUND(HttpStatus.NOT_FOUND, "자소서를 찾을 수 없습니다."),
    AI_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "지금은 AI 기능을 쓸 수 없습니다. 잠시 후 다시 시도해 주세요."),
    AI_FAILED(HttpStatus.BAD_GATEWAY, "AI 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요."),
    FEEDBACK_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "요청이 많습니다. 잠시 후 다시 시도해 주세요."),
    INTERVIEW_NOT_FOUND(HttpStatus.NOT_FOUND, "면접 기록을 찾을 수 없습니다."),
    INTERVIEW_AI_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "면접 AI를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요."),
    INTERVIEW_AI_FAILED(HttpStatus.BAD_GATEWAY, "면접 AI 처리에 실패했습니다. 잠시 후 다시 시도해 주세요."),
    ROOM_NOT_FOUND(HttpStatus.NOT_FOUND, "검토 방을 찾을 수 없습니다."),
    AGENT_NOT_SUPPORTED(HttpStatus.BAD_REQUEST, "지원하지 않는 에이전트입니다."),
    AGENT_NOT_IN_ROOM(HttpStatus.BAD_REQUEST, "이 방에 없는 에이전트입니다."),
    AGENT_CONFIG_REQUIRED(HttpStatus.BAD_REQUEST, "에이전트 설정이 비어 있습니다."),
    COMPANY_RAG_NOT_INDEXED(HttpStatus.BAD_REQUEST, "아직 분석 자료가 준비되지 않은 기업입니다."),
    TURN_IN_PROGRESS(HttpStatus.CONFLICT, "이전 요청이 아직 끝나지 않았습니다."),
    TURN_NOT_FOUND(HttpStatus.NOT_FOUND, "요청 기록을 찾을 수 없습니다."),
    AGENT_SOURCE_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "이 에이전트가 볼 자료가 아직 준비되지 않았습니다."),
    ANALYSIS_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "요청이 많습니다. 잠시 후 다시 시도해 주세요."),
    JOB_POSTING_PARSE_FAILED(HttpStatus.BAD_REQUEST,
            "공고에서 회사명과 직무를 찾지 못했습니다. 공고 주소를 확인하거나 직접 입력해 주세요."),
    JOB_POSTING_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "요청이 많습니다. 잠시 후 다시 시도해 주세요."),
    INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "서버 오류가 발생했습니다.");

    private final HttpStatus status;
    private final String defaultMessage;

    ErrorCode(HttpStatus status, String defaultMessage) {
        this.status = status;
        this.defaultMessage = defaultMessage;
    }

    public HttpStatus getStatus() {
        return status;
    }

    public String getDefaultMessage() {
        return defaultMessage;
    }
}
