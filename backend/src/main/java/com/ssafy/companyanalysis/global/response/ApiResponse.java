package com.ssafy.companyanalysis.global.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.ssafy.companyanalysis.global.error.ErrorCode;

/**
 * 모든 API 응답의 공통 봉투.
 *
 * <p>성공이면 {@code data}만, 실패면 {@code error}만 직렬화된다.
 * 명세(기업분석 API 명세서)의 형태와 동일하다.
 *
 * <pre>
 * { "success": true,  "data": { ... } }
 * { "success": false, "error": { "code": "COMPANY_NOT_FOUND", "message": "..." } }
 * </pre>
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ApiResponse<T>(boolean success, T data, ApiError error) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(true, data, null);
    }

    public static ApiResponse<Void> fail(ErrorCode errorCode, String message) {
        return new ApiResponse<>(false, null, new ApiError(errorCode.name(), message));
    }

    public record ApiError(String code, String message) {
    }
}
