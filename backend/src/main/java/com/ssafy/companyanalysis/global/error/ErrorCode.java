package com.ssafy.companyanalysis.global.error;

import org.springframework.http.HttpStatus;

/**
 * 응답의 {@code error.code} 로 나가는 값.
 *
 * <p>INVALID_PARAMETER · METRIC_NOT_SUPPORTED · COMPANY_NOT_FOUND 는 명세에 정의된 코드다.
 * INTERNAL_ERROR 는 명세가 5xx의 존재만 언급하고 코드를 정하지 않아 여기서 신설했다.
 */
public enum ErrorCode {

    INVALID_PARAMETER(HttpStatus.BAD_REQUEST, "요청 파라미터가 올바르지 않습니다."),
    METRIC_NOT_SUPPORTED(HttpStatus.BAD_REQUEST, "지원하지 않는 지표입니다."),
    COMPANY_NOT_FOUND(HttpStatus.NOT_FOUND, "해당 기업을 찾을 수 없습니다."),
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
