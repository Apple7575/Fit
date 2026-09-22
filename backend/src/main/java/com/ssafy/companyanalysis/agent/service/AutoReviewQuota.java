package com.ssafy.companyanalysis.agent.service;

import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;

/**
 * 자동 검토 한 바퀴가 쓰는 한도 한 장.
 *
 * <p>한 바퀴가 1회다. 방 하나를 1회로 세면 자소서 하나에 방이 여섯이라 화면에 서너 번 들어오는
 * 것만으로 시간당 한도가 바닥난다. 사용자는 검토를 한 번 부탁했을 뿐인데 여섯 번으로 세는 것은
 * 세는 쪽이 틀린 것이다.
 *
 * <p>실제로 돌릴 방을 만났을 때 처음 한 번만 센다. 이미 다 검토된 방만 도는 바퀴는 한도를
 * 쓰지 않는다 — 화면을 다시 열었다는 이유로 깎이면 안 된다.
 */
class AutoReviewQuota {

    private final AnalysisRateLimiter rateLimiter;
    private final Long userId;

    /** null 이면 아직 세지 않았다. */
    private Boolean allowed;

    AutoReviewQuota(AnalysisRateLimiter rateLimiter, Long userId) {
        this.rateLimiter = rateLimiter;
        this.userId = userId;
    }

    /** 이 바퀴가 검토를 돌려도 되는지. 여러 번 물어도 한도는 한 번만 센다. */
    boolean allowed() {
        if (allowed == null) {
            allowed = grant();
        }
        return allowed;
    }

    private boolean grant() {
        try {
            rateLimiter.check(userId);
            return true;
        } catch (BusinessException e) {
            if (e.getErrorCode() != ErrorCode.ANALYSIS_RATE_LIMITED) {
                throw e;
            }
            return false;
        }
    }
}
