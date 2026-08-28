package com.ssafy.companyanalysis.global.error;

/**
 * 서비스 계층에서 의도적으로 던지는 예외. 던진 {@link ErrorCode} 가 그대로 응답이 된다.
 */
public class BusinessException extends RuntimeException {

    private final ErrorCode errorCode;

    public BusinessException(ErrorCode errorCode) {
        this(errorCode, errorCode.getDefaultMessage());
    }

    public BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public ErrorCode getErrorCode() {
        return errorCode;
    }
}
