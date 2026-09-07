package com.ssafy.companyanalysis.focus.service;

import com.ssafy.companyanalysis.company.repository.CompanyRepository;
import com.ssafy.companyanalysis.focus.dto.CompanyActivitiesResponse;
import com.ssafy.companyanalysis.focus.repository.ActivityProjection;
import com.ssafy.companyanalysis.focus.repository.CompanyActivityRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.global.error.ErrorCode;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;

@Service
public class CompanyActivityService {

    /**
     * 명세가 정한 유형 네 종. 테이블의 CHECK 제약과 같은 문자열이고 API 의 type 값이기도 하다.
     *
     * <p>프론트도 같은 목록을 갖고 있다(features/focus-areas/types.ts 의 ACTIVITY_TYPES).
     * 유형이 늘면 명세·테이블·여기·프론트 네 군데를 함께 고쳐야 한다.
     */
    private static final Set<String> ACTIVITY_TYPES =
            Set.of("facility", "corporate_invest", "ma", "transfer");

    private final CompanyRepository companyRepository;
    private final CompanyActivityRepository companyActivityRepository;

    public CompanyActivityService(CompanyRepository companyRepository,
                                  CompanyActivityRepository companyActivityRepository) {
        this.companyRepository = companyRepository;
        this.companyActivityRepository = companyActivityRepository;
    }

    /**
     * 한 기업의 투자·M&A 이벤트를 유형별로 조회한다. 없는 기업은 404 COMPANY_NOT_FOUND 다.
     *
     * <p>이벤트가 없으면 빈 배열이다. 투자 공시를 낸 적 없는 기업은 흔하고 그것은 조회
     * 실패가 아니다.
     *
     * @param type 명세가 정한 네 종 중 하나. 목록에 없으면 400 INVALID_PARAMETER
     * @param from 시작 회계연도. 생략하면 아래로 제한하지 않는다
     * @param to   끝 회계연도. 생략하면 위로 제한하지 않는다
     */
    @Transactional(readOnly = true)
    public CompanyActivitiesResponse getActivities(String corpCode, String type, Integer from, Integer to) {
        requireCompany(corpCode);
        requireKnownType(type);
        requireOrderedRange(from, to);

        List<ActivityProjection> rows = companyActivityRepository.findActivities(corpCode, type, from, to);

        return new CompanyActivitiesResponse(rows.stream()
                .map(row -> new CompanyActivitiesResponse.Item(
                        row.getYear(), row.getType(), row.getField(), row.getPurpose(), row.getAmount()))
                .toList());
    }

    private void requireCompany(String corpCode) {
        if (!companyRepository.existsById(corpCode)) {
            throw new BusinessException(ErrorCode.COMPANY_NOT_FOUND);
        }
    }

    /**
     * 모르는 유형은 400 이다. 조용히 빈 배열을 돌려주지 않는다.
     *
     * <p>오타를 "그 유형의 이벤트가 없는 기업"으로 오해하게 되고, 화면은 아무것도 안 나오는
     * 이유를 알 수 없다. 지표 슬러그 검증과 같은 판단이다.
     */
    private void requireKnownType(String type) {
        if (!ACTIVITY_TYPES.contains(type)) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "지원하지 않는 이벤트 유형입니다.");
        }
    }

    /** 구간이 거꾸로면 400 이다. 시계열 조회와 같은 규칙이다. */
    private void requireOrderedRange(Integer from, Integer to) {
        if (from != null && to != null && from > to) {
            throw new BusinessException(ErrorCode.INVALID_PARAMETER, "from 은 to 보다 클 수 없습니다.");
        }
    }
}
