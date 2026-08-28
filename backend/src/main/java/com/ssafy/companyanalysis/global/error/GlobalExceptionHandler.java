package com.ssafy.companyanalysis.global.error;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.ErrorResponseException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/**
 * 모든 예외를 명세의 오류 봉투로 변환한다.
 *
 * <p>예외 메시지를 그대로 내보내지 않는다. 클라이언트에는 {@link ErrorCode} 의 고정 문구만 나가고,
 * 원인은 서버 로그에만 남긴다. 스택트레이스·SQL·내부 경로가 응답에 실리는 것을 막기 위해서다.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /** 서비스가 의도적으로 던진 예외. 메시지를 상황에 맞게 넘길 수 있어 그대로 사용한다. */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusiness(BusinessException e) {
        ErrorCode errorCode = e.getErrorCode();
        log.warn("business error: code={}, message={}", errorCode.name(), e.getMessage());
        return toResponse(errorCode, e.getMessage());
    }

    /**
     * 파라미터 누락·타입 불일치·검증 실패. 어떤 값이 문제였는지는 로그로만 남긴다.
     *
     * <p>ConstraintViolationException 은 {@code @Validated} 컨트롤러의 쿼리·경로 파라미터
     * 제약(@NotBlank, @Min 등)이 깨질 때 나온다. 이걸 빠뜨리면 사용자 입력 오류가
     * catch-all 로 떨어져 500 이 되므로 반드시 함께 잡는다.
     */
    @ExceptionHandler({
            MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class,
            HandlerMethodValidationException.class,
            MethodArgumentNotValidException.class,
            ConstraintViolationException.class
    })
    public ResponseEntity<ApiResponse<Void>> handleInvalidParameter(Exception e) {
        log.warn("invalid parameter: {}", e.getMessage());
        return toResponse(ErrorCode.INVALID_PARAMETER, ErrorCode.INVALID_PARAMETER.getDefaultMessage());
    }

    /**
     * Spring 이 상태코드를 실어 던지는 예외(없는 경로 404, 허용되지 않은 메서드 405 등).
     * 명세에 이 경우의 코드가 없어 4xx 는 INVALID_PARAMETER, 5xx 는 INTERNAL_ERROR 로 보낸다.
     * 상태코드는 Spring 이 정한 값을 그대로 유지해 FE 가 상태별로 분기할 수 있게 한다.
     */
    @ExceptionHandler(ErrorResponseException.class)
    public ResponseEntity<ApiResponse<Void>> handleErrorResponse(ErrorResponseException e) {
        HttpStatusCode status = e.getStatusCode();
        ErrorCode errorCode = status.is4xxClientError() ? ErrorCode.INVALID_PARAMETER : ErrorCode.INTERNAL_ERROR;
        log.warn("spring error response: status={}, message={}", status, e.getMessage());
        return ResponseEntity.status(status)
                .body(ApiResponse.fail(errorCode, errorCode.getDefaultMessage()));
    }

    /** 위에서 걸러지지 않은 모든 예외. 원인은 스택트레이스와 함께 로그에만 남긴다. */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpected(Exception e) {
        log.error("unexpected error", e);
        return toResponse(ErrorCode.INTERNAL_ERROR, ErrorCode.INTERNAL_ERROR.getDefaultMessage());
    }

    private ResponseEntity<ApiResponse<Void>> toResponse(ErrorCode errorCode, String message) {
        return ResponseEntity.status(errorCode.getStatus())
                .body(ApiResponse.fail(errorCode, message));
    }
}
