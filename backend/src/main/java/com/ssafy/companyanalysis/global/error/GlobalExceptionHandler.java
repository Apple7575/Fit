package com.ssafy.companyanalysis.global.error;

import com.ssafy.companyanalysis.global.response.ApiResponse;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.ObjectError;
import org.springframework.web.ErrorResponse;
import org.springframework.web.ErrorResponseException;
import org.springframework.web.HttpMediaTypeNotAcceptableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Set;

/**
 * 모든 예외를 명세의 오류 봉투로 변환한다.
 *
 * <p>예외 메시지를 그대로 내보내지 않는다. 클라이언트에는 {@link ErrorCode} 의 고정 문구나
 * 우리가 사람에게 하려고 적어 둔 안내만 나가고, 원인은 서버 로그에만 남긴다.
 * 스택트레이스·SQL·내부 경로가 응답에 실리는 것을 막기 위해서다.
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
     * 파라미터 누락·타입 불일치·검증 실패·본문 파싱 실패. 어떤 값이 문제였는지는 로그로만 남긴다.
     *
     * <p>ConstraintViolationException 은 {@code @Validated} 컨트롤러의 쿼리·경로 파라미터
     * 제약(@NotBlank, @Min 등)이 깨질 때 나온다. 이걸 빠뜨리면 사용자 입력 오류가
     * catch-all 로 떨어져 500 이 되므로 반드시 함께 잡는다.
     *
     * <p>고정 문구("요청 파라미터가 올바르지 않습니다")만 내보내면 받은 사람이 무엇을 고쳐야
     * 할지 알 수 없다. 그래서 제약에 사람 말로 적어 둔 안내가 있으면 그것을 대신 보낸다.
     */
    @ExceptionHandler({
            MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class,
            HandlerMethodValidationException.class,
            MethodArgumentNotValidException.class,
            ConstraintViolationException.class,
            HttpMessageNotReadableException.class
    })
    public ResponseEntity<ApiResponse<Void>> handleInvalidParameter(Exception e) {
        log.warn("invalid parameter: {}", e.getMessage());
        String written = writtenMessage(e);
        return toResponse(ErrorCode.INVALID_PARAMETER,
                written != null ? written : ErrorCode.INVALID_PARAMETER.getDefaultMessage());
    }

    /**
     * 깨진 제약 중 우리가 사람에게 할 말을 적어 둔 것을 찾는다. 없으면 null.
     *
     * <p>제약에 {@code message} 를 적지 않으면 Bean Validation 이 기본 문구를 만든다 —
     * {@code "technical|behavioral"와 일치해야 합니다} 처럼 규칙을 그대로 읽어 준다.
     * 그건 개발자끼리 쓰는 말이고, 애초에 화면이 고르게 하는 값이라 사용자가 고칠 수도 없다.
     * 그래서 기본 문구는 절대 내보내지 않고, 직접 적어 둔 것만 골라 보낸다.
     *
     * <p>가려내는 기준은 메시지 서식이다. 기본 문구는 {@code {jakarta.validation...message}} 처럼
     * 중괄호로 싸인 키로 남고, 직접 적은 것은 그 자리에 사람 말이 그대로 있다.
     *
     * <p>여러 칸이 한꺼번에 걸리면 그중 하나만 말한다. 한 번에 한 칸씩 짚어 주는 편이
     * 어디부터 고칠지 고민하지 않아도 되어 빠르다(프론트의 사전 검증도 같은 규칙이다).
     */
    private static String writtenMessage(Exception e) {
        if (e instanceof MethodArgumentNotValidException invalid) {
            // @RequestBody 본문 검증. Spring 이 ConstraintViolation 을 오류마다 싸 두었다.
            for (ObjectError error : invalid.getBindingResult().getAllErrors()) {
                if (!error.contains(ConstraintViolation.class)) continue;
                String message = writtenMessage(error.unwrap(ConstraintViolation.class));
                if (message != null) return message;
            }
        }
        if (e instanceof ConstraintViolationException violated) {
            // @Validated 컨트롤러의 쿼리·경로 파라미터. 목록이 비어 있을 수 있다.
            Set<ConstraintViolation<?>> violations = violated.getConstraintViolations();
            if (violations == null) return null;
            for (ConstraintViolation<?> violation : violations) {
                String message = writtenMessage(violation);
                if (message != null) return message;
            }
        }
        return null;
    }

    /** 직접 적어 둔 안내면 그 문구, 기본 문구면 null */
    private static String writtenMessage(ConstraintViolation<?> violation) {
        String template = violation.getMessageTemplate();
        if (template == null || (template.startsWith("{") && template.endsWith("}"))) return null;
        return violation.getMessage();
    }

    /**
     * Spring 이 상태코드를 실어 던지는 예외(없는 경로 404, 허용되지 않은 메서드 405 등).
     * 명세에 이 경우의 코드가 없어 4xx 는 INVALID_PARAMETER, 5xx 는 INTERNAL_ERROR 로 보낸다.
     * 상태코드는 Spring 이 정한 값을 그대로 유지해 FE 가 상태별로 분기할 수 있게 한다.
     *
     * <p>이 예외들은 공통 부모 클래스가 없어 {@link ErrorResponse} 로 받는다. 나열한 타입은 모두
     * 이 인터페이스를 구현해야 한다. 구현하지 않는 타입(HttpMessageNotReadableException)을 넣으면
     * 파라미터 바인딩에 실패해 본문 없는 응답이 나간다.
     */
    @ExceptionHandler({
            ErrorResponseException.class,
            HttpRequestMethodNotSupportedException.class,
            NoResourceFoundException.class,
            NoHandlerFoundException.class,
            HttpMediaTypeNotSupportedException.class,
            HttpMediaTypeNotAcceptableException.class
    })
    public ResponseEntity<ApiResponse<Void>> handleErrorResponse(ErrorResponse e) {
        HttpStatusCode status = e.getStatusCode();
        ErrorCode errorCode = status.is4xxClientError() ? ErrorCode.INVALID_PARAMETER : ErrorCode.INTERNAL_ERROR;
        log.warn("spring error response: status={}, type={}, detail={}",
                status, e.getClass().getSimpleName(), e.getBody().getDetail());
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
