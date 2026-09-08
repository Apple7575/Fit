"""데이터 사전 `docs/data_fields.csv` 를 만든다.

    python scripts/build_data_fields.py

기계로 읽을 수 있는 것(테이블·컬럼·순서·타입·NULL·키·FK·SQL COMMENT)은 Flyway 에서
읽고, 사람만 아는 것(출처 서비스·원본 필드명·변환 규칙·예시·개인정보 여부)은 아래
`ANNOTATIONS` 에 적는다. 사전을 통째로 손으로 관리하면 마이그레이션이 하나 늘 때마다
조용히 낡는다 — 그래서 절반을 기계에 맡기고, `scripts/verify_news.py` 9번이 남은
절반의 누락을 잡는다.

확인할 수 없는 것은 추측하지 않고 remarks 에 "합의 필요" 라고 적는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news import flyway  # noqa: E402
from pipeline.news.csvio import write_csv  # noqa: E402

FIELDS = [
    "table_name", "column_name", "ordinal_position", "data_type", "nullable",
    "key_type", "referenced_table", "referenced_column", "description",
    "provider", "source_field", "transform_rule", "example",
    "contains_personal_data", "remarks",
]

# provider — 값을 실제로 준 쪽. 여러 계층을 거쳐도 최초 출처를 적는다.
OPENDART = "opendart"                    # DART OpenAPI 정형 엔드포인트
FILING = "opendart_filing"               # OpenDART 로 받은 사업보고서 원문 XML
NEWS = "google_news_rss"                 # Google 뉴스 RSS (NewsData.io 가 아니다)
DERIVED = "derived"                      # 파이프라인 계산 결과
AI = "ai_analysis"                       # 외부 모델 생성물
FLYWAY = "flyway_seed"                   # 마이그레이션 SQL 이 넣는 값
DB = "database"                          # DB 기본값
UNSET = "미정"                            # 적재 경로가 아직 없다

AGREEMENT = "합의 필요"

# 테이블별 기본 provider. 컬럼 단위로 덮어쓸 수 있다.
TABLE_PROVIDER = {
    "industry": FLYWAY,
    "metric": FLYWAY,
    "company": OPENDART,
    "company_metric": DERIVED,
    "metric_evidence": DERIVED,
    "dart_financial_account": OPENDART,
    "dart_employee_status": OPENDART,
    "staging.dart_otr_cpr_invstmnt": OPENDART,
    "collection_run": DERIVED,
    "company_business": FILING,
    "company_product": FILING,
    "company_segment": FILING,
    "company_rnd_field": FILING,
    "company_focus_direction": AI,
    "company_focus_direction_item": AI,
    "company_activity": OPENDART,
    "company_news": NEWS,
}

# (provider, source_field, transform_rule, example, contains_personal_data, remarks)
# source_field 가 빈 값이면 원본 필드가 없는 파생·관리 컬럼이다.
A = {}


def note(table, column, provider=None, source_field="", transform_rule="raw",
         example="", personal="no", remarks=""):
    A[(table, column)] = dict(provider=provider, source_field=source_field,
                              transform_rule=transform_rule, example=example,
                              contains_personal_data=personal, remarks=remarks)


# ── 공통 관리 컬럼 ────────────────────────────────────
for table, column in (
    ("company", "created_at"), ("company", "updated_at"),
    ("company_metric", "updated_at"), ("company_business", "updated_at"),
    ("company_product", "updated_at"), ("company_segment", "updated_at"),
    ("company_rnd_field", "updated_at"), ("company_activity", "updated_at"),
):
    note(table, column, DB, "", "default:now()", "2026-09-07T12:00:00+09:00")

# ── industry / metric ─────────────────────────────────
note("industry", "industry_code", FLYWAY, "ksic_division.csv:ksic_division", "raw", "26",
     remarks="V3 이 config/ksic_division.csv 77건을 시드한다. KSIC 중분류 2자리")
note("industry", "industry_name", FLYWAY, "ksic_division.csv:division_name", "raw",
     "전자부품, 컴퓨터, 영상, 음향 및 통신장비 제조업")
note("metric", "metric_code", FLYWAY, "", "constant", "revenue",
     remarks="V2·V4·V5·V7 이 시드한다. API 경로변수 {metric} 값")
note("metric", "name_ko", FLYWAY, "", "constant", "매출액")
note("metric", "unit", FLYWAY, "", "constant", "KRW", remarks="KRW/PERSON/YEAR/% 4종")
note("metric", "value_scale", FLYWAY, "", "constant", "0")
note("metric", "source_type", FLYWAY, "", "constant", "FINANCIAL_STATEMENT")
note("metric", "display_order", FLYWAY, "", "constant", "1")
note("metric", "is_active", FLYWAY, "", "constant", "true")
note("metric", "is_core", FLYWAY, "", "constant", "true", remarks="V7 에서 추가")

# ── company ───────────────────────────────────────────
note("company", "corp_code", OPENDART, "corpCode.xml:corp_code", "raw", "00126380")
note("company", "corp_name", OPENDART, "company_universe.csv:corp_name", "derived:종목명 우선",
     "삼성전자", remarks="DART 등록명이 아니라 종목명. targets.csv 의 display_name 으로 덮어쓴다 (V6)")
note("company", "corp_name_eng", OPENDART, "company.json:corp_name_eng", "raw", "SAMSUNG ELECTRONICS CO,.LTD")
note("company", "stock_code", OPENDART, "corpCode.xml:stock_code", "raw", "005930",
     remarks="비상장사는 NULL")
note("company", "corp_cls", OPENDART, "company.json:corp_cls", "raw", "Y")
note("company", "industry_code", OPENDART, "company.json:induty_code", "derived:KSIC 중분류 2자리로 축약", "26")
note("company", "ceo_nm", OPENDART, "company.json:ceo_nm", "raw", "한종희", personal="yes",
     remarks="공시된 대표자 성명. 개인 식별 정보이므로 화면·로그 노출 범위를 따로 본다")
note("company", "established_date", OPENDART, "company.json:est_dt", "derived:YYYYMMDD → DATE", "1969-01-13")
note("company", "listed_date", UNSET, "", "미적재", "",
     remarks="기업개황 응답에 상장일 필드가 없다. KRX 등 별도 소스 필요")
note("company", "dart_modify_date", OPENDART, "corpCode.xml:modify_date", "raw", "20260301")
note("company", "induty_code", OPENDART, "company.json:induty_code", "raw", "26410",
     remarks="DART 5자리 세분류 원본 보존용")
note("company", "address", OPENDART, "company.json:adres", "raw", "경기도 수원시 영통구 …")
note("company", "homepage_url", OPENDART, "company.json:hm_url", "raw", "www.samsung.com/sec",
     remarks="스킴이 없는 형태로 오는 경우가 있다")

# ── DART 착지 테이블 ──────────────────────────────────
note("dart_financial_account", "id", DB, "", "identity", "1")
note("dart_financial_account", "corp_code", OPENDART, "요청 파라미터 corp_code", "raw", "00126380")
note("dart_financial_account", "bsns_year", OPENDART, "요청 파라미터 bsns_year", "raw", "2025")
note("dart_financial_account", "reprt_code", OPENDART, "fnlttSinglAcntAll:reprt_code", "raw", "11011")
note("dart_financial_account", "fs_div", OPENDART, "fnlttSinglAcntAll:fs_div", "raw", "CFS")
note("dart_financial_account", "sj_div", OPENDART, "fnlttSinglAcntAll:sj_div", "raw", "IS")
note("dart_financial_account", "account_nm", OPENDART, "fnlttSinglAcntAll:account_nm", "raw", "매출액")
note("dart_financial_account", "thstrm_amount", OPENDART, "fnlttSinglAcntAll:thstrm_amount",
     "derived:콤마 제거 후 수치화", "300870903000000")
note("dart_financial_account", "collected_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")

note("dart_employee_status", "id", DB, "", "identity", "1")
note("dart_employee_status", "corp_code", OPENDART, "요청 파라미터 corp_code", "raw", "00126380")
note("dart_employee_status", "bsns_year", OPENDART, "요청 파라미터 bsns_year", "raw", "2025")
note("dart_employee_status", "reprt_code", OPENDART, "empSttus:reprt_code", "raw", "11011")
note("dart_employee_status", "fo_bbm", OPENDART, "empSttus:fo_bbm", "derived:없으면 빈 문자열", "DX부문")
note("dart_employee_status", "sexdstn", OPENDART, "empSttus:sexdstn", "derived:없으면 빈 문자열", "남")
note("dart_employee_status", "rgllbr_co", OPENDART, "empSttus:rgllbr_co", "derived:콤마 제거", "74000")
note("dart_employee_status", "cnttk_co", OPENDART, "empSttus:cnttk_co", "derived:콤마 제거", "1200")
note("dart_employee_status", "sm", OPENDART, "empSttus:sm", "derived:콤마 제거", "75200")
note("dart_employee_status", "avrg_cnwk_sdytrn", OPENDART, "empSttus:avrg_cnwk_sdytrn", "raw", "13년 2개월",
     remarks="회사별 표기가 제각각이라 원문 TEXT 로 보존하고 파싱은 정규화 단계에서 한다")
note("dart_employee_status", "fyer_salary_totamt", OPENDART, "empSttus:fyer_salary_totamt",
     "derived:콤마 제거", "9200000000000")
note("dart_employee_status", "jan_salary_am", OPENDART, "empSttus:jan_salary_am", "derived:콤마 제거", "122000000",
     remarks="사업부문별 1인평균이라 단순평균하면 안 된다")
note("dart_employee_status", "collected_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")

for column, source, example, remark in (
    ("id", "", "1", "identity"),
    ("corp_code", "요청 파라미터 corp_code", "00164779", ""),
    ("bsns_year", "요청 파라미터 bsns_year", "2025", ""),
    ("reprt_code", "otrCprInvstmntSttus:reprt_code", "11011", ""),
    ("row_no", "응답 배열 순번", "0", "원문 순서 보존"),
    ("rcept_no", "otrCprInvstmntSttus:rcept_no", "20260310002820", ""),
    ("is_total", "", "false", "합계 행 판정. config/patterns.yaml investment.total_row_re"),
    ("inv_prm", "otrCprInvstmntSttus:inv_prm", "SK스퀘어", ""),
    ("invstmnt_purps", "otrCprInvstmntSttus:invstmnt_purps", "단순투자(보통주)", ""),
    ("frst_acqs_de", "otrCprInvstmntSttus:frst_acqs_de", "1977.01.01", "원문 표기 보존"),
    ("frst_acqs_de_iso", "", "1977-01-01", "frst_acqs_de 파싱값. 못 읽으면 NULL"),
    ("frst_acqs_amount", "otrCprInvstmntSttus:frst_acqs_amount", "1000000000", ""),
    ("bsis_blce_qy", "otrCprInvstmntSttus:bsis_blce_qy", "1000", ""),
    ("bsis_blce_qota_rt", "otrCprInvstmntSttus:bsis_blce_qota_rt", "20.15", ""),
    ("bsis_blce_acntbk_amount", "otrCprInvstmntSttus:bsis_blce_acntbk_amount", "5000000000", ""),
    ("incrs_dcrs_acqs_dsps_qy", "otrCprInvstmntSttus:incrs_dcrs_acqs_dsps_qy", "0", ""),
    ("incrs_dcrs_acqs_dsps_amount", "otrCprInvstmntSttus:incrs_dcrs_acqs_dsps_amount", "0", ""),
    ("incrs_dcrs_evl_lstmn", "otrCprInvstmntSttus:incrs_dcrs_evl_lstmn", "0", ""),
    ("trmend_blce_qy", "otrCprInvstmntSttus:trmend_blce_qy", "1000", ""),
    ("trmend_blce_qota_rt", "otrCprInvstmntSttus:trmend_blce_qota_rt", "20.15", ""),
    ("trmend_blce_acntbk_amount", "otrCprInvstmntSttus:trmend_blce_acntbk_amount", "5000000000", ""),
    ("recent_tot_assets", "otrCprInvstmntSttus:recent_tot_assets", "10000000000",
     "피출자회사의 총자산. 우리 회사 값이 아니다"),
    ("recent_thstrm_ntpf", "otrCprInvstmntSttus:recent_thstrm_ntpf", "500000000",
     "피출자회사의 당기순이익"),
    ("stlm_dt", "otrCprInvstmntSttus:stlm_dt", "2024-12-31", ""),
    ("collected_at", "", "2026-09-07T12:00:00+09:00", "default:now()"),
):
    rule = "raw" if source else ("identity" if column == "id" else "derived")
    if column == "collected_at":
        rule = "default:now()"
    note("staging.dart_otr_cpr_invstmnt", column, OPENDART if source else DB, source, rule,
         example, remarks=remark)

# ── 지표·근거 ─────────────────────────────────────────
note("company_metric", "corp_code", DERIVED, "dart_financial_account.corp_code", "raw", "00126380")
note("company_metric", "fiscal_year", DERIVED, "dart_financial_account.bsns_year", "raw", "2025")
note("company_metric", "metric_code", DERIVED, "", "derived:지표 카탈로그 매핑", "revenue")
note("company_metric", "metric_value", DERIVED, "dart_financial_account.thstrm_amount",
     "derived:pipeline/normalize 규칙", "300870903000000")
note("company_metric", "fs_div", DERIVED, "dart_financial_account.fs_div", "raw", "CFS",
     remarks="파생·비재무 지표는 NULL")

note("metric_evidence", "corp_code", DERIVED, "", "raw", "00126380")
note("metric_evidence", "fiscal_year", DERIVED, "", "raw", "2025")
note("metric_evidence", "metric_code", DERIVED, "", "raw", "rd_cost")
note("metric_evidence", "verdict", DERIVED, "", "derived:교차검증 판정", "verified")
note("metric_evidence", "source", DERIVED, "", "derived:획득 경로", "doc_table")
note("metric_evidence", "rcept_no", FILING, "document.xml:rcept_no", "raw", "20260310002820")
note("metric_evidence", "evidence", DERIVED, "", "derived:표 순번·행 라벨·원문 셀",
     '{"table_idx":110,"row_label":"연구개발비용 총계","raw":"37,754,815"}')
note("metric_evidence", "gap_pct", DERIVED, "", "derived:회사 기재값과의 차이", "0.0312")
note("metric_evidence", "warnings", DERIVED, "", "derived:정규화 경고", "{}")
note("metric_evidence", "collected_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")

note("collection_run", "id", DB, "", "identity", "1")
note("collection_run", "run_type", DERIVED, "", "constant", "FINANCIAL",
     remarks="CORP_CODE/COMPANY_PROFILE/FINANCIAL/EMPLOYEE/INVESTMENT. 뉴스 유형은 없다 — 합의 필요")
note("collection_run", "target_year", DERIVED, "", "raw", "2025")
note("collection_run", "status", DERIVED, "", "constant", "SUCCESS")
note("collection_run", "started_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")
note("collection_run", "finished_at", DERIVED, "", "raw", "2026-09-07T12:03:00+09:00")
note("collection_run", "success_count", DERIVED, "", "derived:실행 집계", "50")
note("collection_run", "fail_count", DERIVED, "", "derived:실행 집계", "0")
note("collection_run", "message", DERIVED, "", "raw", "")

# ── 사업보고서 기반 ───────────────────────────────────
for table, column, example in (
    ("company_business", "business_name", "DX부문"),
    ("company_product", "product_name", "메모리"),
    ("company_rnd_field", "field_name", "차세대 메모리"),
):
    note(table, column, FILING, "document.xml:사업의 내용", "derived:추출 PoC 결과", example,
         remarks="S15P21A504-73 추출 방식 확정 전. 현재 미적재")
for table in ("company_business", "company_product", "company_rnd_field", "company_segment",
              "company_focus_direction", "company_focus_direction_item", "company_activity"):
    note(table, "corp_code", None, "company.corp_code", "raw", "00126380")
    note(table, "fiscal_year", None, "", "derived:사업연도", "2025")
for table in ("company_business", "company_product", "company_rnd_field",
              "company_focus_direction_item"):
    note(table, "display_order", None, "", "derived:기재 순서 보존", "1")
note("company_segment", "segment_code", FILING, "document.xml:부문 표기", "raw", "DX",
     remarks="기업별 표기 그대로. 표준 코드체계가 없다")
note("company_segment", "revenue", FILING, "document.xml:부문 매출", "derived:원 단위", "1000000000000",
     remarks="미공시는 NULL 이며 0 과 다른 사실이다")
note("company_segment", "employee_count", FILING, "document.xml:부문 인력", "raw", "75200",
     remarks="미공시는 NULL")
note("company_segment", "updated_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")

note("company_focus_direction", "strategy_change", AI, "", "derived:모델 생성물", "",
     remarks="공시 수치가 아니다. 화면에서 AI 분석으로 구분 표시한다. 현재 미적재")
note("company_focus_direction", "generated_at", DB, "", "default:now()", "2026-09-07T12:00:00+09:00")
note("company_focus_direction_item", "item_type", AI, "", "constant", "NEW_BUSINESS")
note("company_focus_direction_item", "item_name", AI, "", "derived:모델 생성물", "로봇",
     remarks="현재 미적재")

note("company_activity", "id", DB, "", "identity", "1")
note("company_activity", "activity_type", OPENDART, "", "constant", "facility",
     remarks="facility/corporate_invest/ma/transfer. API 의 type 파라미터 값과 같다")
note("company_activity", "field_name", OPENDART, "주요사항보고서", "derived:추출 결과", "파운드리")
note("company_activity", "purpose", OPENDART, "주요사항보고서", "derived:추출 결과", "미국 테일러 공장 생산능력 확대")
note("company_activity", "amount", OPENDART, "주요사항보고서", "derived:원 단위", "44000000000000")
note("company_activity", "rcept_no", OPENDART, "주요사항보고서:rcept_no", "raw", "20260310002820")

# ── company_news — 뉴스 원본 필드와 DB 컬럼의 매핑 ────
# source_field 는 "RSS 필드 → staged 컬럼" 으로 적는다. 원본 그대로인 값과 파생값을
# transform_rule 로 가른다. AI 컬럼은 적재 경로가 아직 없다.
note("company_news", "id", DB, "", "identity", "1",
     remarks="GENERATED ALWAYS AS IDENTITY. 시드 CSV 에 넣지 않는다")
note("company_news", "corp_code", DERIVED, "requests.json:query → staged.corp_code",
     "derived:검색어를 company_universe.csv 의 corp_name·dart_corp_name 과 정확·정규화 일치로 매핑",
     "00126380",
     remarks="RSS 에 기업 식별자가 없다. 매핑 실패 행은 시드에 넣지 않고 사유를 남긴다")
note("company_news", "title", NEWS, "rss:item/title → staged.title",
     "derived:끝의 ' - <언론사>' 접미사만 제거", "삼성전자, 테일러 공장 가동", personal="possible",
     remarks="기사 제목에 인물명이 들어올 수 있다. 제3자 저작물이므로 저장·표시 조건 확인 필요")
note("company_news", "description", NEWS, "rss:item/description → staged.description",
     "derived:검토를 통과한 요약만. 제목 반복은 넣지 않는다", "",
     remarks="현재 전부 NULL. RSS 설명이 제목 반복인 사례가 있어 요약으로 쓰지 않는다 (90번 문서)")
note("company_news", "published_at", NEWS, "rss:item/pubDate → staged.published_at",
     "derived:RFC 2822 → UTC ISO 8601. 시간대 누락은 NULL", "2026-09-05T23:30:00+00:00",
     remarks="저장은 UTC, 기간 구분은 KST(staged.published_date_kst), 응답은 서울 기준 날짜")
note("company_news", "original_url", NEWS, "rss:item/link → staged.original_url",
     "derived:Google 경유 주소가 아닌 외부 링크만 후보로 남긴다", "https://n.example/article/1",
     remarks="Google 경유 rss_link 를 여기 넣지 않는다. 외부 링크도 접근 검증 전 후보다")
note("company_news", "source", NEWS, "rss:item/source → staged.publisher",
     "derived:기본 publisher", "테스트일보",
     remarks=f"{AGREEMENT} — 컬럼이 하나뿐이라 provider(google_news_rss)와 publisher(언론사)를 "
             "함께 담을 수 없다. provider 컬럼 추가를 제안한다")
note("company_news", "category", AI, "", "미적재", "",
     remarks="AI 분류 미실행. 팀이 카테고리 분류를 하지 않기로 했고 프론트 어휘는 7종이다 — 합의 필요")
note("company_news", "related_business", AI, "", "미적재", "",
     remarks="AI 분석 PoC 단계(S15P21A504-74). 반복 안정성 미달로 적재하지 않는다")
note("company_news", "importance_score", AI, "", "미적재", "",
     remarks="0~10. NULL 은 분석 실패이고 0 과 다른 사실이다")
note("company_news", "analyzed_at", AI, "", "미적재", "",
     remarks="분석을 돌린 시각. 기본 필드만 적재된 뉴스는 NULL")
note("company_news", "collected_at", NEWS, "requests.json:checked_at → staged.collected_at",
     "raw", "2026-09-06T00:10:00+00:00",
     remarks="원본을 받은 시각. DB 기본값 now() 에 맡기지 않고 수집 시각을 넣는다")

# ── V13 이 만든 표 — segment_metric · company_text · news_article ────
# segment_metric 과 company_activity.counterparty 는 시드가 있으므로 채운다
# (scripts/build_curated_seed.py). 나머지는 적재 경로가 없어 합의 필요로 둔다.
note("segment_metric", "corp_code", OPENDART, "empSttus:corp_code", "raw", "00126380")
note("segment_metric", "fiscal_year", OPENDART, "empSttus 요청의 bsns_year", "raw", "2024")
note("segment_metric", "segment_name", OPENDART, "empSttus:fo_bbm",
     "derived:공백 정리 후 성별 행을 접어 부문 하나로. 합계 행('성별합계' 등)은 뺀다", "DX",
     remarks="연도별 자연키다. 회사가 부문 이름을 바꾸면 다른 부문이 된다")
note("segment_metric", "metric_code", DERIVED, "", "constant",
     "segment_employee_count",
     remarks="부문마다 segment_revenue·segment_employee_count 두 행을 항상 만든다")
note("segment_metric", "metric_value", OPENDART, "empSttus:sm",
     "derived:부문 안의 성별 행 합계. segment_revenue 는 원천이 없어 NULL", "112456",
     remarks="NULL 은 그 부문이 이 지표를 공시하지 않았다는 사실이며 0 과 다르다")
note("segment_metric", "updated_at", DB, "", "default:now()", "2026-09-08T12:00:00+09:00")
note("company_activity", "counterparty", OPENDART,
     "otrCprInvstmntSttus:inv_prm", "derived:공백 정리", "삼성전기㈜",
     remarks="피출자회사. 현재 /activities 응답에는 나가지 않는다")

for _column in ("id", "corp_code", "fiscal_year", "attr_key", "seq", "value_text",
                "generated_at", "updated_at"):
    note("company_text", _column, UNSET, "", "미적재", "",
         remarks=f"{AGREEMENT} — 사업보고서 추출 PoC 가 진행 중이라 적재 경로가 없다. "
                 "attr_key 에 따라 원천이 사업보고서 원문과 AI 생성물로 갈린다")

for _column in ("id", "corp_code", "title", "description", "published_at",
                "original_url", "source", "news_category", "related_business",
                "importance_score", "analyzed_at", "collected_at"):
    note("news_article", _column, NEWS, "", "미적재", "",
         remarks=f"{AGREEMENT} — V13 이 company_news 를 이 이름으로 옮겼는데 "
                 "scripts/build_news_seed.py 가 아직 옛 이름으로 쓴다. "
                 "매핑은 위 company_news 항목과 같다")

# ── V14 · V15 인증 표 ─────────────────────────────────
# 수집 파이프라인이 아니라 애플리케이션이 채운다. 시드 대상이 아니다.
for _column in ("id", "email", "password_hash", "nickname", "role", "status",
                "created_at", "updated_at"):
    note("users", _column, DB, "", "미적재", "",
         personal="yes" if _column in ("email", "password_hash", "nickname") else "no",
         remarks="회원 가입이 만드는 값이다. 시드 CSV 가 없다")
for _column in ("id", "user_id", "token_hash", "expires_at", "used_at"):
    note("email_verification_token", _column, DB, "", "미적재", "",
         personal="yes" if _column == "user_id" else "no",
         remarks="이메일 인증이 만드는 값이다. 시드 CSV 가 없다")


# SQL COMMENT 가 없는 컬럼의 설명. 있는 것은 COMMENT 를 그대로 쓴다.
DESC = {
    ("collection_run", "run_type"): "수집 배치 종류",
    ("collection_run", "target_year"): "대상 사업연도. 연도 개념이 없는 실행은 NULL",
    ("collection_run", "status"): "RUNNING/SUCCESS/FAILED",
    ("collection_run", "started_at"): "실행 시작 시각",
    ("collection_run", "finished_at"): "실행 종료 시각. 진행 중이면 NULL",
    ("collection_run", "success_count"): "성공 건수",
    ("collection_run", "fail_count"): "실패 건수",
    ("collection_run", "message"): "실패 원인·비고",
    ("company", "corp_name_eng"): "영문 회사명",
    ("company", "listed_date"): "상장일",
    ("company", "created_at"): "이 행을 처음 넣은 시각",
    ("company", "updated_at"): "이 행을 마지막으로 고친 시각",
    ("industry", "industry_name"): "KSIC 중분류 명칭",
    ("metric", "name_ko"): "지표 한글명. 응답의 name",
    ("metric", "display_order"): "화면 표시 순서",
    ("company_metric", "fiscal_year"): "회계연도",
    ("company_metric", "metric_code"): "지표 코드. metric 카탈로그를 참조한다",
    ("company_metric", "updated_at"): "이 값을 마지막으로 적재한 시각",
    ("metric_evidence", "fiscal_year"): "회계연도",
    ("metric_evidence", "metric_code"): "지표 코드",
    ("dart_financial_account", "corp_code"): "DART 고유번호 8자리",
    ("dart_financial_account", "bsns_year"): "사업연도",
    ("dart_financial_account", "account_nm"): "DART 응답의 계정명 원문",
    ("dart_financial_account", "thstrm_amount"): "당기 금액(원)",
    ("dart_financial_account", "collected_at"): "이 행을 적재한 시각",
    ("dart_employee_status", "corp_code"): "DART 고유번호 8자리",
    ("dart_employee_status", "bsns_year"): "사업연도",
    ("dart_employee_status", "reprt_code"): "보고서 코드. 11011=사업보고서",
    ("dart_employee_status", "rgllbr_co"): "정규직 인원",
    ("dart_employee_status", "cnttk_co"): "계약직 인원",
    ("dart_employee_status", "collected_at"): "이 행을 적재한 시각",
    ("company_news", "corp_code"): "이 뉴스를 붙인 기업. DART 고유번호 8자리",
    ("company_news", "original_url"): "언론사 직접 원문 URL. 확보하지 못하면 NULL",
    ("company_news", "collected_at"): "원본을 받은 시각",
    ("company_activity", "corp_code"): "DART 고유번호 8자리",
    ("company_activity", "fiscal_year"): "회계연도",
    ("company_activity", "updated_at"): "이 행을 마지막으로 적재한 시각",
    ("company_focus_direction_item", "item_name"): "신규사업명 또는 전략 키워드",
    ("company_rnd_field", "field_name"): "R&D 중점 분야명",
}
for _table in ("company_business", "company_product", "company_rnd_field", "company_segment",
               "company_focus_direction", "company_focus_direction_item", "company_metric",
               "metric_evidence"):
    DESC[(_table, "fiscal_year")] = "회계연도. 사업 구성은 해마다 바뀌므로 키에 들어간다"
    DESC[(_table, "corp_code")] = "DART 고유번호 8자리. company 를 참조한다"
for _table in ("company_business", "company_product", "company_rnd_field", "company_segment"):
    DESC[(_table, "updated_at")] = "이 행을 마지막으로 적재한 시각"
for _column, _text in (
    ("corp_code", "DART 고유번호 8자리"),
    ("bsns_year", "사업연도"),
    ("reprt_code", "보고서 코드. 11011=사업보고서"),
    ("rcept_no", "근거 공시 접수번호 14자리"),
    ("frst_acqs_amount", "최초 취득 금액(원)"),
    ("bsis_blce_qy", "기초 잔액 수량"),
    ("bsis_blce_qota_rt", "기초 지분율(%)"),
    ("bsis_blce_acntbk_amount", "기초 장부가액(원)"),
    ("incrs_dcrs_acqs_dsps_qy", "증감 중 취득·처분 수량"),
    ("incrs_dcrs_acqs_dsps_amount", "증감 중 취득·처분 금액(원)"),
    ("trmend_blce_qy", "기말 잔액 수량"),
    ("trmend_blce_qota_rt", "기말 지분율(%)"),
    ("collected_at", "이 행을 적재한 시각"),
):
    DESC[("staging.dart_otr_cpr_invstmnt", _column)] = _text
for _table in ("dart_financial_account", "dart_employee_status", "collection_run",
               "company_activity", "company_news", "staging.dart_otr_cpr_invstmnt"):
    DESC.setdefault((_table, "id"), "대리 키. DB 가 생성하며 시드 CSV 에 넣지 않는다")

# V13 · V14 · V15 가 만든 표 중 SQL COMMENT 가 없는 컬럼.
for _table in ("company_text", "segment_metric"):
    DESC[(_table, "corp_code")] = "DART 고유번호 8자리. company 를 참조한다"
    DESC[(_table, "fiscal_year")] = "회계연도. 사업 구성은 해마다 바뀌므로 키에 들어간다"
    DESC[(_table, "updated_at")] = "이 행을 마지막으로 적재한 시각"
DESC[("company_text", "id")] = "대리 키. DB 가 생성하며 시드 CSV 에 넣지 않는다"
DESC[("segment_metric", "metric_code")] = \
    "지표 코드. metric 을 참조하며 segment_revenue · segment_employee_count 두 값을 쓴다"
for _column, _text in (
    ("corp_code", "DART 고유번호 8자리. company 를 참조한다"),
    ("title", "기사 제목"),
    ("description", "기사 요약. 제목 반복은 넣지 않는다"),
    ("published_at", "기사 발행 시각(UTC). 시간대를 알 수 없으면 NULL"),
    ("original_url", "기사 원문 주소. Google 경유 주소가 아닌 외부 링크다"),
    ("related_business", "AI 가 연결한 사업 영역. 미분석은 NULL"),
    ("importance_score", "AI 중요도 0~10. NULL 은 분석 실패이고 0 과 다른 사실이다"),
    ("collected_at", "원본을 받은 시각"),
):
    DESC[("news_article", _column)] = _text
for _column, _text in (
    ("id", "대리 키. DB 가 생성한다"),
    ("email", "로그인 아이디로 쓰는 이메일 주소"),
    ("nickname", "화면에 보이는 이름"),
    ("role", "권한 등급"),
    ("status", "계정 상태"),
    ("created_at", "가입 시각"),
    ("updated_at", "이 행을 마지막으로 고친 시각"),
):
    DESC[("users", _column)] = _text
for _column, _text in (
    ("id", "대리 키. DB 가 생성한다"),
    ("user_id", "토큰 주인. users 를 참조한다"),
    ("expires_at", "만료 시각. 지나면 인증에 쓸 수 없다"),
    ("used_at", "사용한 시각. 아직 안 썼으면 NULL"),
):
    DESC[("email_verification_token", _column)] = _text


def main() -> int:
    schema = flyway.load()
    rows = []
    for table in sorted(schema.tables.values(), key=lambda t: (t.schema, t.name)):
        default_provider = TABLE_PROVIDER.get(table.qualified, "")
        for column in table.ordered():
            extra = A.get((table.qualified, column.name), {})
            provider = extra.get("provider") or default_provider
            rows.append({
                "table_name": table.qualified,
                "column_name": column.name,
                "ordinal_position": column.ordinal,
                "data_type": column.data_type,
                "nullable": "YES" if column.nullable else "NO",
                "key_type": column.key_type,
                "referenced_table": column.referenced_table,
                "referenced_column": column.referenced_column,
                "description": column.comment or DESC.get((table.qualified, column.name), ""),
                "provider": provider,
                "source_field": extra.get("source_field", ""),
                "transform_rule": extra.get("transform_rule", ""),
                "example": extra.get("example", ""),
                "contains_personal_data": extra.get("contains_personal_data", "no"),
                "remarks": extra.get("remarks", ""),
            })
    path = Path(__file__).resolve().parents[1] / "docs" / "data_fields.csv"
    write_csv(path, FIELDS, rows)
    print(f"{path.name}  {len(rows)}행 / {len(schema.tables)}개 테이블 "
          f"({len(schema.applied_files)}개 마이그레이션 기준)")
    gaps = 0
    for label, key in (("변환 규칙", "transform_rule"), ("설명", "description")):
        missing = [f"{r['table_name']}.{r['column_name']}" for r in rows if not r[key]]
        if missing:
            gaps += 1
            print(f"{label} 없는 컬럼 {len(missing)}개: {', '.join(missing[:15])}")
    print(f"'합의 필요' 표시 {sum('합의 필요' in r['remarks'] for r in rows)}개 컬럼")
    return 1 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
