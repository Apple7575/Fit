"""뉴스 staged·curated 컬럼 규격과 상수.

컬럼 목록을 한 곳에 두는 이유는 정제(stage)·적재본 생성(curate)·검증(verify)이
같은 순서를 봐야 하기 때문이다. 세 곳에 각각 적어 두면 컬럼을 하나 늘릴 때
검증만 옛 목록을 보고 통과시켜 버린다.
"""
from __future__ import annotations

# ── 출처 ──────────────────────────────────────────────
# provider 는 데이터를 전달한 서비스, publisher 는 기사를 발행한 언론사다. 둘을 한
# 필드에 섞지 않는다. 실제 수집 경로는 Google 뉴스 RSS 이며(news.google.com/rss/search)
# NewsData.io 가 아니다 — docs/news-poc/90-source-review.md 참고.
PROVIDER = "google_news_rss"

# RSS 요청이 hl=ko, gl=KR, ceid=KR:ko 로 고정되어 있어 언어·국가는 상수다.
# 수집기가 이 값을 바꾸면 여기도 같이 바뀌어야 한다.
LANGUAGE = "ko"
COUNTRY = "KR"

# 정제 코드 규격 버전. staged 산출물과 manifest 에 함께 남겨 재생성 결과를 대조한다.
STAGE_SCHEMA_VERSION = "news-staged-v1"
SEED_SCHEMA_VERSION = "news_article-seed-v1"
MANIFEST_SCHEMA_VERSION = "news-manifest-v1"

# ── staged ────────────────────────────────────────────
# 원본에서 재생성 가능한 정제 결과. 원본 문자열(published_at_raw·rss_link)과 파생값
# (published_at·published_date_kst)을 나란히 둔다. 파생값만 남기면 파싱 규칙이 바뀐 뒤
# 원본을 다시 읽을 방법이 없다.
STAGED_FIELDS = [
    # 식별자
    "article_key",            # 수집기가 만든 안정 식별자 (GUID → 정규화 URL → 제목+언론사+시각)
    "collection_run_id",      # 어느 수집 실행에서 나왔나
    "source_raw_file",        # 원본 XML 파일명
    "source_record_index",    # 그 파일 안 item 순번 (0부터)
    # 기업 연결
    "corp_code",              # DART 고유번호 8자리. 매핑 실패는 빈 값
    "query_company_name",     # 수집에 사용한 검색어(회사명)
    "corp_map_method",        # 어떤 규칙으로 붙였나
    "corp_map_reason",        # 붙이지 못한 이유
    # 기사 본문 필드
    "title",
    "title_checksum",         # 제목 SHA-256. 중복 판정 보조값
    "description",            # 검토를 통과한 요약만. 현재 수집기는 항상 빈 값
    "description_raw",        # RSS description 을 텍스트로 벗긴 값
    "description_status",     # missing / title_repeat / needs_review
    # 링크
    "original_url",           # 언론사 직접 원문 후보
    "original_url_norm",      # 중복 판정용 정규화 URL
    "original_url_status",    # rss_direct_unverified / unresolved
    "rss_link",               # Google 뉴스 경유 주소. 원문 주소가 아니다
    "google_url",
    "guid",
    "image_url",              # RSS 미제공. 항상 빈 값
    # 출처
    "provider",
    "publisher",
    "publisher_url",
    # 시각
    "published_at",           # UTC ISO 8601
    "published_at_raw",       # RSS pubDate 원문
    "published_date_kst",     # KST 기준 날짜. 기간 필터·일자 집계 기준
    "collected_at",           # 원본을 받은 시각 (requests.json 의 checked_at)
    # 언어·국가
    "language",
    "country",
    # 상태
    "stage_status",           # staged / unresolved_corp
    "is_duplicate",           # true 면 대표 행이 아니다
    "duplicate_of",           # 대표 행의 article_key
    "duplicate_rule",         # 어느 규칙으로 중복 판정했나
    "quality_issues",         # 수집기가 남긴 입력 결함 (missing_title 등)
    "stage_schema_version",
]

# 정제에서 떨어진 행. 버리지 않고 사유와 함께 남긴다.
REJECT_FIELDS = STAGED_FIELDS + ["reject_reason"]

# ── curated seed ──────────────────────────────────────
# news_article(V13) 컬럼과 헤더가 일치해야 한다. id 는 GENERATED ALWAYS AS IDENTITY 라
# OVERRIDING SYSTEM VALUE 없이 INSERT 할 수 없으므로 CSV 에 넣지 않는다.
#
# V13 이 V12 의 company_news 를 확정 ERD 이름인 news_article 로 옮기고 category 를
# news_category 로 바꿨다. 나머지 컬럼 구성은 그대로다 — source·collected_at·analyzed_at
# 도 남았다. 시드 파일명·manifest 이름이 이 상수에서 나오므로 여기만 바꾸면 따라온다.
SEED_TABLE = "news_article"
SEED_IDENTITY_COLUMNS = ["id"]
SEED_FIELDS = [
    "corp_code",
    "title",
    "description",
    "published_at",
    "original_url",
    "source",
    "news_category",
    "related_business",
    "importance_score",
    "analyzed_at",
    "collected_at",
]

# news_article.source 가 provider·publisher 중 무엇을 담는지는 백엔드와 합의가 필요하다
# (V13 주석도 "수집 출처"로만 적혀 있다). 기본값은 publisher 다 —
# provider 는 manifest·staged 에 상수로 남아 있어 잃을 것이 없는데, publisher 는
# 현재 스키마에 다른 자리가 없어 버리면 언론사 표시 근거가 사라진다.
SEED_SOURCE_CHOICES = ("publisher", "provider")
SEED_SOURCE_DEFAULT = "publisher"

# ── 중복 판정 규칙 ────────────────────────────────────
# 제목이 같다는 이유만으로 지우지 않는다. 아래 순서로 보고, 앞 규칙에서 같다고 본 것만
# 중복으로 판정한다. 같은 사건을 다룬 다른 기사는 중복이 아니다.
DUPLICATE_RULES = (
    "article_key",                       # 수집기 식별자가 같다
    "original_url_norm",                 # 정규화된 직접 원문 주소가 같다
    "title_checksum+published_date_kst", # 제목 체크섬과 KST 발행일이 모두 같다
)
