# 데이터 저장 기준

`data/` 아래 파일이 어디에 있어야 하고 무엇을 커밋하는지 정한다. 하나의 `data/` 영역에서
관리하되 **원본은 출처별로 분리하고 가공 이후에만 서비스용 데이터로 통합한다.**

이 문서가 저장 위치·파일명·Git 추적 범위의 정본이다. 파싱 규칙과 지표 판정 근거는
[`DESIGN.md`](DESIGN.md), 뉴스 PoC 의 판정 이력은 [`news-poc/`](news-poc/) 에 있다.

- 작성자: 데이터 담당 (tpdms3048)
- 날짜: 2026-09-07
- 관련: 팀 공통 데이터 관리 기준 (Jira 이슈 없음 — 팀장 요청)

---

## 1. 세 단계

| 단계 | 뜻 | 고칠 수 있나 | 커밋 |
|---|---|---|---|
| `raw` | 외부 서비스에서 받은 그대로 | **아니다.** 읽기만 한다 | 안 한다 |
| `staged` | 날짜·컬럼명·결측·기업 식별자를 표준화한 결과 | 코드로 재생성한다 | 안 한다 |
| `curated` | DB 테이블에 바로 적재할 최종 데이터 | 코드로 재생성한다 | 한다 (뉴스는 예외, 7장) |

원칙 셋.

1. **원본은 불변이다.** 컬럼명·값을 고치지 않고, 중복 기사를 지우지 않고, AI 카테고리·중요도·요약
   같은 가공 필드를 원본에 넣지 않는다. 기존 원본 파일을 새 수집 결과로 덮어쓰지 않는다.
2. **staged 와 curated 는 raw 에서 재생성 가능해야 한다.** 그래서 수동 편집을 전제한 컬럼을 두지
   않는다. 손으로 고친 값은 다음 실행에서 사라진다.
3. **원본과 정제본과 적재본을 같은 CSV·같은 폴더에 섞지 않는다.** 파일명이 비슷하다는 이유로
   같은 데이터라고 판단하지 않는다 — 어느 파일이 정본인지는 8장에 적어 둔다.

### 출처별 분류

| 데이터 | 원천 | 단계상 위치 |
|---|---|---|
| DART 정형 API (기업개황·재무제표·직원현황·타법인출자) | OpenDART | `raw/opendart/api/` |
| 사업보고서 원문 XML | OpenDART `document.xml` | `raw/opendart/filings/annual_report/` |
| 뉴스 기사 후보 | Google 뉴스 RSS | `raw/google_news_rss/articles/` |

사업보고서는 OpenDART 로 받지만 **정형 API 응답이 아니라 공시 원문**이다. 파싱 방식·검증
규칙·실패 양상이 전혀 달라 같은 폴더에 두면 재처리 단위가 섞인다. 계보상 출처가 OpenDART 라는
사실은 유지하므로 `opendart/` 아래 `filings/` 로 가른다.

### 뉴스 출처 이름 — NewsData.io 가 아니다

이 저장소의 뉴스 데이터는 **Google 뉴스 RSS** 에서 온다
(`data/news_poc/pipeline/collect.py` → `news.google.com/rss/search`). `newsdata` 라는 이름의
서비스는 코드·문서·설정 어디에도 없다. 그래서 폴더와 `provider` 값은 실제 출처명
`google_news_rss` 를 쓴다.

`provider` 와 `publisher` 를 한 필드에 섞지 않는다.

- `provider` = 데이터를 전달한 서비스. 현재 값은 `google_news_rss` 하나뿐이다
- `publisher` = 실제 기사를 발행한 언론사

Google RSS 가 **운영 소스로 확정된 것은 아니다.** 저장·캐싱·AI 활용 조건이 미확정이고 robots
사전 점검은 disallowed 다 ([`news-poc/90-source-review.md`](news-poc/90-source-review.md)).
7장의 Git 추적 정책이 그 판단에 따라 정해져 있다.

---

## 2. 디렉터리 구조

```text
data/
├── config/                          적재·수집 입력 (기업 유니버스·타깃·패턴)
├── raw/                             원본. 읽기 전용, Git 제외
│   ├── opendart/
│   │   ├── api/                     정형 API 응답
│   │   └── filings/
│   │       └── annual_report/       사업보고서 원문 XML
│   └── google_news_rss/
│       └── articles/
│           └── <collection_run_id>/ *.xml · requests.json · run.json
├── staged/                          정제 결과. 재생성 가능, Git 제외
│   ├── opendart/
│   ├── business_report/             segment_revenue · facility · main_product ·
│   │                                rd_expense · passages.jsonl · text_llm.csv
│   └── google_news_rss/
│       └── <collection_run_id>/     articles.csv · rejects.csv · duplicates.csv · stage_summary.json
├── curated/
│   └── seed/                        <table_name>.csv — DB 적재본
├── manifests/                       계보 기록. Git 추적
│   ├── google_news_rss/             <collection_run_id>.json
│   └── seed/                        <table_name>.json
├── logs/                            실행 로그
│   └── google_news_rss/
├── pipeline/                        수집·정규화 코드
│   └── news/                        뉴스 raw → staged → curated
├── scripts/                         CLI
├── docs/                            이 문서 · data_fields.csv · seed_csv_inventory.csv
└── tests/
    └── fixtures/                    회귀 검증 기준선
```

### 아직 이 구조에 있지 않은 것

| 현재 위치 | 기준상 위치 | 왜 안 옮겼나 |
|---|---|---|
| `data/.cache/*.json` (DART 정형 API) | `raw/opendart/api/` | 기존 파이프라인이 평면 파일명을 직접 만들고 읽는다 (`pipeline/paths.py` · `pipeline/rawstore.py` · `scripts/load_raw.py` · `scripts/load_company.py`). 옮기면 수집·정규화·적재·검증이 함께 바뀐다 |
| `data/.cache/document_*.xml` (사업보고서) | `raw/opendart/filings/annual_report/` | 위와 같다 |
| `data/_out/*.csv` | `staged/opendart/` 또는 `curated/seed/` | `scripts/normalize.py` · `report_gaps.py` · `verify_db.py` 가 경로를 상수로 쓴다 |
| `data/_log/*.csv` | `logs/` | `pipeline/paths.py` 의 `LOG` 가 가리킨다 |

**이번 브랜치에서는 옮기지 않았다.** DART 캐시·산출물 마이그레이션은 별도 작업으로 남긴다
(12장). [`DESIGN.md`](DESIGN.md) 6장이 raw 레이아웃을 `data/raw/<endpoint>_<key>.json` 평면
구조로 적어 두었으나 구현은 `data/.cache/` 를 쓴다 — 그 문서가 구현보다 앞서 있었던 것이고,
위 표의 「기준상 위치」가 앞으로의 목표다.

---

## 3. 파일명 규칙

| 대상 | 규칙 | 예 |
|---|---|---|
| 뉴스 수집 실행 폴더 | `<YYYYMMDDThhmmssZ>-<8자리 hex>` | `20260906T001000Z-abcdef01` |
| 뉴스 원본 XML | 수집기가 만든 요청 계획 해시 `.xml` | `a1b2c3d4e5f6a7b8c9d0.xml` |
| 뉴스 요청 이력 | `requests.json` (수집기 산출) | |
| 뉴스 들여오기 기록 | `run.json` (대상 구간·체크섬) | |
| 수집 manifest | `manifests/<provider>/<collection_run_id>.json` | |
| staged | `staged/<provider>/<collection_run_id>/articles.csv` | |
| 시드 CSV | `curated/seed/<table_name>.csv` | `curated/seed/news_article.csv` |
| 시드 manifest | `manifests/seed/<table_name>.json` | |

**경로에 회사명을 주요 식별자로 쓰지 않는다.** 한 실행이 여러 기업을 다룰 수 있고, 회사명을
박으면 같은 기업을 재조회할 때 폴더가 겹쳐 원본을 덮어쓴다. 수집 대상 회사명은 경로가 아니라
`requests.json` 의 쿼리와 manifest 의 `companies` 에 남는다.

---

## 4. 식별자 규칙

| 대상 | 식별자 | 근거 |
|---|---|---|
| 기사 | `article_key` — GUID → 정규화된 링크 → `제목+언론사+발행시각` 순으로 만든 SHA-256 | Google RSS 가 기사 ID 를 따로 주지 않는다. 수집기(`normalize.parse_feed`)가 만들고 정제는 그 값을 그대로 쓴다 |
| 기업 | `corp_code` (DART 고유번호 8자리) | RSS 에 기업 식별자가 없다. 검색어(회사명)를 `config/company_universe.csv` 의 `corp_name`·`dart_corp_name` 과 **정확일치 또는 표기 정규화 일치**로만 붙인다 |
| 수집 실행 | `collection_run_id` (폴더명) | manifest·staged·시드 manifest 를 잇는 키 |
| 언론사 | `publisher` 문자열 + `publisher_url` | 표준 코드체계가 없다 |

기업 매핑은 **추정하지 않는다.** 부분일치·유사도로 붙이면 "삼성전자" 검색 결과가 삼성전기에
붙는 오류가 조용히 DB 로 들어간다. 자동으로 붙지 않는 경우는 이렇게 처리한다.

- `corp_code` 를 비우고 `corp_map_reason` 에 사유를 남긴다
  (`not_in_company_universe` / `ambiguous_name:<n>_candidates` / `empty_query_company_name`)
- 그 행은 `stage_status = unresolved_corp` 이고 **시드 CSV 에 넣지 않는다** (FK 위반)
- 사람이 확인해 `config/` 에 별칭을 추가하는 것이 후속 작업이다

`SK하이닉스` ↔ `에스케이하이닉스(주)` 처럼 음차 표기가 다른 경우는 표기 정규화로도 붙지 않는다.
사전을 만드는 것은 추정이 아니라 사람의 확인이므로 별도 작업으로 남긴다.

---

## 5. 시각과 시간대

| 값 | 저장 형식 |
|---|---|
| `published_at` (raw → staged → DB) | UTC ISO 8601. 원문은 `published_at_raw` 에 그대로 남긴다 |
| `published_date_kst` (staged) | KST 기준 날짜. **기간 필터와 일자 집계의 기준** |
| `collected_at` | UTC ISO 8601 (`requests.json` 의 `checked_at`) |
| API 응답 | 서울 기준 날짜 `YYYY-MM-DD` (백엔드가 잘라서 내보낸다) |

저장은 UTC, 날짜 구분은 KST, 노출은 서울 날짜다. 시간대를 읽을 수 없으면 **추정하지 않고
`published_at` 을 비운 뒤** `rejects.csv` 의 `unparsed_published_at` 으로 분리한다.
DB 는 `published_at` NULL 을 허용하지만 그 행은 세 뉴스 API 어디에도 나가지 않는다
(`V12__company_news.sql` 주석. 테이블은 `V13` 에서 `news_article` 로 옮겨졌다).

---

## 6. 중복 판정

제목이 같다는 이유만으로 지우지 않는다. 아래 순서로 보고 **앞 규칙에서 같다고 본 것만** 중복으로
판정한다. 판정된 행은 지우지 않고 `duplicates.csv` 로 분리하며 `duplicate_of`·`duplicate_rule` 을
남긴다.

1. `article_key` 가 같다
2. 정규화된 직접 원문 주소(`original_url_norm`)가 같다 — 추적 파라미터(`utm_*` 등)만 떼고
   기사 식별자 쿼리(`?idxno=`)는 남긴다
3. 제목 체크섬과 KST 발행일이 **모두** 같다

같은 사건을 다룬 다른 기사는 중복이 아니다. 재조회에서 다시 관측되지 않은 기사를 삭제된 것으로
보지 않는다 — 같은 날짜 재조회에서도 결과가 달라진 실측이 있다
([`news-poc/91-collection-result.md`](news-poc/91-collection-result.md)).

**지금 DB 는 URL 중복을 막지 않는다.** V12 의 부분 UNIQUE 인덱스
`(corp_code, original_url) WHERE original_url IS NOT NULL` 이 V13 의 `news_article` 로
넘어오지 않았다 — 복원을 요청해 두었다
([`S15P21A504-v13-followup.md`](S15P21A504-v13-followup.md) 2장). 그래서 **시드 생성의
같은 조건 판정(`pipeline/news/curate.py`)이 유일한 방어다.** 우리 파이프라인을 통과할
때만 걸리므로 DB 레벨 방어가 아니라는 점을 알고 써야 한다.

V17 이 확정 ERD 의 다른 중복 방지 키 `UNIQUE (corp_code, guid)` 를 넣었다. 이쪽은 DB 가
막는다. 다만 RSS 가 guid 를 주지 않으면 NULL 이고 NULL 끼리는 충돌하지 않으므로,
URL 판정을 대신하지는 못한다.

---

## 7. Git 추적 범위

| 대상 | 추적 | 이유 |
|---|---|---|
| `raw/**` | **제외** (`.gitkeep` 만) | DART 캐시가 330MB 이상이고, 뉴스 RSS 는 저장·재배포 조건이 미확정이다 |
| `staged/**` | **제외** (`.gitkeep` 만) | raw 에서 재생성 가능하다. `_out/` 과 같은 판단 |
| `curated/seed/*.csv` | 추적 | 팀이 DB 를 채우는 입력이다 |
| `curated/seed/news_article.csv` | **제외** | 제3자 기사 제목·URL 을 담는다. 사용조건 확정까지 커밋하지 않는다. 옛 이름 `company_news.csv` 도 함께 제외한다 |
| `manifests/**` | 추적 | 기사 내용이 아니라 건수·해시·요청 이력만 들어 있다. 원본을 커밋하지 않으므로 저장소에 남는 **유일한 계보 기록**이다 |
| `logs/**` | 제외 | 저장소 루트 `.gitignore` 의 `logs/` 규칙에 이미 걸린다. 실행 산출물이라 그대로 둔다 |
| `docs/data_fields.csv` · `docs/seed_csv_inventory.csv` | 추적 | 문서다 |

`data/logs/` 는 루트 규칙 때문에 `.gitkeep` 조차 추적되지 않는다. 폴더가 필요한 사람은
스크립트가 만들거나 직접 만든다. 추적이 필요해지면 루트 `.gitignore` 에 `!data/logs/` 를
더해야 하고, 그건 팀 전체 정책 변경이므로 임의로 하지 않았다.

### 대용량·라이선스 데이터 공유

**현재 결정 없음 — 합의 필요.** 확인해야 하는 것은 세 가지다.

1. 상장사 뉴스 제목·발행일·언론사·링크를 정기 수집해 DB 에 저장·갱신해도 되는가. 허용 주기와
   보관기간은 얼마인가
2. 화면에 표시할 때 필요한 출처·링크 표시 조건은 무엇인가
3. 제목·설명을 외부 AI API 에 보내 추론하고 결과를 저장해도 되는가

답을 얻기 전까지 뉴스 원본과 뉴스 시드는 커밋하지 않는다. 그동안의 공유 방법은 **파일 직접
전달**이며(`local_raw/`·`local_output/` 폴더 전달), `.env` 와 API 키는 포함하지 않는다.
저장소에는 manifest 만 남으므로 건수·해시·수집 시각은 파일 없이도 대조할 수 있다.

---

## 8. 정본(canonical source)

같은 데이터가 여러 곳에 있을 때 어느 것을 믿는지 정한다. 임시 복사본을 두 번째 원본으로
만들지 않는다.

| 데이터 | 정본 | 나머지 |
|---|---|---|
| DART 정형 API 응답 | `data/.cache/*.json` | `_out/*.csv` 는 검수용 산출물 |
| 사업보고서 원문 | `data/.cache/document_*.xml` | |
| 뉴스 원본 | `raw/google_news_rss/articles/<run_id>/*.xml` | 수집기의 `local_output/` 은 PoC 산출물 |
| 뉴스 정제본 | `staged/google_news_rss/<run_id>/articles.csv` | |
| 기업 마스터 적재 입력 | `curated/seed/company.csv` (2,703건) | `config/company_universe.csv` 는 그 시드의 원천이다 |
| 산업 분류 | Flyway `V3` + `config/ksic_division.csv` | `curated/seed/industry.csv` 는 같은 77건이고 대조에만 쓴다 |
| 지표 카탈로그 | Flyway `V2`·`V4`·`V5`·`V7`·`V13` | `curated/seed/metric.csv` 는 SQL 의 사본이다 |
| 지표 값 | `company_metric` 테이블 (`scripts/load_metrics.py` 가 `.cache` 에서 정규화해 적재) | 전 종목분은 `curated/seed/company_metric.csv` |
| DB 스키마 | `backend/src/main/resources/db/migration/V*.sql` | `docs/data_fields.csv` 는 이 SQL 에서 생성한다 |

루트 CSV 3종(`company.csv`·`industry.csv`·`company_metric.csv`)은 **지웠다.**
`curated/seed/` 의 재생성본이 같은 표를 더 넓게 담아 같은 표를 가리키는 파일이 둘이
되었기 때문이다 (MR !81 에서 팀장 확인). 옛 `company_metric.csv` 에만 있던 직원·R&D
지표 187행은 10개사 정규화 경로(`scripts/normalize.py` → `_out/`)가 계속 만들고 DB 에도
있다. `company_year_wide.csv` 와 `manifest.json` 은 남긴다 — 보조 산출물이고
`rnd_cost_krw` 가 QA 용으로 거기에만 있다.

---

## 9. 시드 CSV 생성 기준

- DB 테이블 하나당 CSV 하나. 파일명은 `<table_name>.csv`
- 헤더는 Flyway 의 **실제 컬럼명과 순서**에 일치. `scripts/verify_news.py` 9번이 대조한다
- 인코딩은 **BOM 없는 UTF-8**, 줄바꿈은 **LF**. `COPY ... ENCODING 'UTF8'` 이 BOM 을 첫
  컬럼명의 일부로 읽고, `\r\n` 으로 쓰면 OS 마다 체크섬이 달라져 재현 검증이 깨진다
- 빈 셀 = SQL NULL. `"null"` 이나 `"-"` 로 채우지 않는다
- 날짜·시각은 ISO 8601 (`2026-09-05T23:30:00+00:00`), 날짜만인 컬럼은 `YYYY-MM-DD`
- enum 은 DB CHECK 제약의 값을 그대로 쓴다 (`facility` / `corporate_invest` / `ma` / `transfer`)
- **identity 컬럼은 넣지 않는다.** `news_article.id` 는 `GENERATED ALWAYS AS IDENTITY` 라
  `OVERRIDING SYSTEM VALUE` 없이 INSERT 할 수 없다
- PK·UNIQUE 중복 금지. FK 대상이 먼저 존재해야 한다 (`industry` → `company` → 나머지)
- 같은 입력으로 다시 실행하면 같은 정렬·같은 바이트. 뉴스 시드는
  `(corp_code, published_at, article_key)` 순이다
- **표본이 아니라 확보된 전체 범위**를 넣는다. 표본이면
  `seed_csv_inventory.csv` 의 `full_or_sample` 에 `sample` 로 적는다
- 길이·범위 위반은 잘라서 통과시키지 않는다. 그 행을 빼고 사유를 남긴다
- 생성 시각·원본 범위·레코드 수·스키마 버전을 `manifests/seed/<table_name>.json` 에 남긴다

### 데이터 필드 CSV

[`data_fields.csv`](data_fields.csv) 는 **데이터 사전이지 시드 CSV 가 아니다.** 실제 데이터를
담지 않는다. 최신 Flyway 스키마 기준으로 17개 테이블 148개 컬럼을 적었고, 절반은 기계가
채운다.

- 기계가 채우는 것: `table_name` · `column_name` · `ordinal_position` · `data_type` ·
  `nullable` · `key_type` · `referenced_table` · `referenced_column` · SQL `COMMENT` 기반 설명
- 손으로 적는 것: `provider` · `source_field` · `transform_rule` · `example` ·
  `contains_personal_data` · `remarks`

`transform_rule` 이 `raw` 면 원본 그대로이고, `derived:…` 면 파생·정규화된 값이다.
뉴스 컬럼의 `source_field` 는 `rss:item/title → staged.title` 처럼 **원본 필드 → staged 컬럼**
으로 적는다. 확인할 수 없는 것은 추측하지 않고 `remarks` 에 `합의 필요` 로 적는다 (현재 3건).

`python scripts/build_data_fields.py` 로 다시 만든다. 마이그레이션이 늘면 사전이 조용히
낡으므로 `scripts/verify_news.py` 9번이 사전과 스키마의 컬럼 집합을 대조한다.

### 테이블별 보유 현황

[`seed_csv_inventory.csv`](seed_csv_inventory.csv). `seed_status` 는 여섯 값만 쓴다.

| 값 | 뜻 |
|---|---|
| `available` | 시드 CSV 가 있고 Git 에 있다 |
| `generated_but_untracked` | 생성되지만 `.gitignore` 대상이다 |
| `sql_seed_only` | Flyway SQL 이 값을 넣는다. CSV 없음 |
| `missing` | 시드가 있어야 하는데 없다 |
| `not_applicable` | 시드 대상이 아니다 (실행 이력·보조 산출물) |
| `schema_not_defined` | 테이블 자체가 없다 |

DB 테이블과 1:1 대응하지 않는 CSV(`company_year_wide.csv` 등)는 시드로 판정하지 않고
`table_name = (테이블 아님)` · `not_applicable` 로 분류한다.

---

## 10. manifest 와 로그

### 수집 manifest — `manifests/google_news_rss/<run_id>.json`

손으로 쓰지 않는다. `scripts/import_news_raw.py` 가 원본 폴더에서 만든다. 담는 것:

`provider` · `collection_run_id` · `collected_at_first`/`_last` · `queries` · `companies` ·
`target_start`/`target_end_exclusive` · 파일별 (`path`, `bytes`, `sha256`, `record_count`,
`http_status`, `collected_at`, `user_agent`, `recorded_sha256_matches`, `possibly_truncated`) ·
`record_count` · `unique_article_keys` · `duplicate_candidate_count` · `request_count` ·
`success_count` · `fail_count` · `failed_queries` · `collector_module` ·
`manifest_schema_version` · `full_coverage_verified`.

`possibly_truncated` 는 응답 100건 이상이라는 **관측 기준**이며 공식 한도가 아니다.
`full_coverage_verified` 는 항상 `false` 다 — 전수 수집을 확인한 적이 없다.

### 시드 manifest — `manifests/seed/<table_name>.json`

생성 시각 · 헤더 · 제외한 identity 컬럼 · Flyway 파일 목록 · 입력 staged 행수 · 시드 행수 ·
제외 행수와 사유 · 기업 수 · 결측 건수 · `source` 컬럼 매핑 · 관련 `collection_run_id` 목록.

### 로그

수집·정제 실행 로그는 `logs/<provider>/` 에 둔다 (Git 제외). 기존 DART 파이프라인은
`_log/ingest_log.csv` · `_log/load_log.csv` 를 계속 쓴다.

---

## 11. 검증

`python scripts/verify_news.py` 가 14개 항목을 돌린다. DB 에 붙지 않는다 — 스키마는 Flyway
SQL 에서 읽고 FK 대조는 `config/company_universe.csv` 로 한다.

| # | 항목 |
|---:|---|
| 1 | 원본 파일 수 ↔ manifest 파일 수 (+ 체크섬 일치) |
| 2 | 원본 레코드 수 ↔ staged 처리 결과 (+ 수집기 집계와 대조) |
| 3 | 제외 레코드·사유 집계 |
| 4 | 기사 식별자 중복 |
| 5 | URL 중복 |
| 6 | `corp_code` 매핑 성공·실패 |
| 7 | `published_at` 파싱 성공·실패 |
| 8 | 필수 컬럼 null (staged + 시드의 NOT NULL) |
| 9 | curated 헤더·데이터 사전 ↔ Flyway 컬럼 |
| 10 | 시드 PK·UNIQUE 중복 |
| 11 | FK 참조 무결성 |
| 12 | `seed_csv_inventory.csv` 의 `row_count` ↔ 실제 행 수 (+ 누락 테이블) |
| 13 | 재실행 결정성 (다시 만들어 바이트 비교) |
| 14 | 단위 테스트 |

**`SKIP` 을 `PASS` 로 세지 않는다.** 원본이 없어 확인하지 못한 것과 확인해서 통과한 것은 다르다.
실패 건수와 원인은 그대로 출력하며, 데이터를 임의로 보정해 통과시키지 않는다.

---

## 12. 이번 브랜치에서 적용한 범위

했다.

- `raw` / `staged` / `curated` / `manifests` / `logs` 디렉터리와 Git 추적 정책
- 뉴스 raw → staged → curated 코드 (`pipeline/news/`) 와 CLI 4종
  (`import_news_raw.py` · `stage_news.py` · `build_news_seed.py` · `verify_news.py`)
- Flyway SQL 파서 (`pipeline/news/flyway.py`) — 검증과 데이터 사전의 기준
- `docs/data_fields.csv` (15 테이블 143 컬럼) · `docs/seed_csv_inventory.csv` (26행) · 이 문서
  — V13 이 테이블 일곱 개를 셋으로 합치고, V14·V15 가 인증 테이블 둘을 더하고,
  V16 이 뉴스 AI 컬럼 넷을 지우고, V17 이 `guid` 를 더한 뒤의 수다
- 단위·통합 테스트 63건

하지 않았다.

- **뉴스 시드 CSV 생성.** 수집 원본이 저장소와 이 작업 트리에 없다. 표본이나 예시 데이터를
  만들지 않았다
- `data/.cache/` 의 DART JSON·사업보고서 XML 이동 — 기존 파이프라인이 평면 경로를 직접 쓴다
- `_out/` · `_log/` · 루트 CSV 이동
- DART 파서·지표 계산·백엔드 API 변경

### 후속 작업

1. 뉴스 원본 폴더 공유 → `import_news_raw.py` → `stage_news.py` → `build_news_seed.py`
2. `news_article.source` 가 `provider` 인지 `publisher` 인지 백엔드와 합의 (기본값은 `publisher`,
   `--source-column provider` 로 전환. `provider` 컬럼 추가를 제안한다)
3. 뉴스 사용조건 확정 → 원본·시드의 Git 추적 정책 재판정
4. `collection_run.run_type` CHECK 에 뉴스 수집 유형 추가 여부
5. 기업명 별칭 사전 (음차 표기) — 매핑 실패를 사람이 확인해 줄인다
6. AI 카테고리·관련사업·중요도 적재 경로 (S15P21A504-74 PoC 이후)
7. DART 캐시·`_out`·루트 CSV 마이그레이션 (별도 작업)
8. `metric_evidence` 시드 CSV 헤더를 DB 컬럼에 맞출지 결정 (`bsns_year` → `fiscal_year` 등)
