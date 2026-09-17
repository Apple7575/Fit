# V13 후속 — DATA 쪽 반영과 백엔드에 남은 셋

> DATA → 백엔드. **1판 (2026-09-08).**
>
> - 작성자: 데이터 담당 (tpdms3048)
> - 대상: `V13__erd_alignment.sql` (`8a487f1`, 2026-09-07 16:40 develop 머지)
> - 관련: `docs/design/db-schema.md` 2-1 · S15P21A504-120

V13 이 머지되면서 파이프라인·문서 쪽이 옛 테이블 이름을 가리키고 있었다. 그것을 맞췄고,
그 과정에서 **V12 에 있던 인덱스 세 개와 컬럼 주석 다섯 개가 V13 으로 넘어오지 않은 것**을
찾았다. 아래 2장이 요청이다.

---

## 1. DATA 쪽에서 고친 것

`company_news` → `news_article`, `category` → `news_category` 를 따라간 것이 대부분이다.
시드 파일명과 manifest 이름은 `pipeline/news/schema.py` 의 `SEED_TABLE` 하나에서 나오므로
상수만 바꾸면 따라온다.

```
pipeline/news/schema.py       SEED_TABLE · SEED_FIELDS · SEED_SCHEMA_VERSION
pipeline/news/curate.py       AI_COLUMNS · 중복 판정 주석
pipeline/news/verify.py       10번 검사 설명
pipeline/news/flyway.py       DROP TABLE · ALTER … SET SCHEMA 를 읽는다  ← 아래 설명
scripts/build_data_fields.py  새 세 테이블의 출처·변환 규칙
docs/data_fields.csv          재생성 — 13 테이블 133 컬럼
docs/seed_csv_inventory.csv   지워진 일곱 행을 빼고 새 세 행을 넣었다 (16행)
docs/DATA_STORAGE_STANDARD.md 경로 예시·추적 정책·후속 작업
.gitignore                    /curated/seed/news_article.csv
tests/news/                   위에 맞춰 갱신 + 파서 테스트 2건 추가
```

**`flyway.py` 가 `DROP TABLE` 을 건너뛰고 있었다.** 파서가 마이그레이션을 순서대로 적용해
현재 스키마를 만드는데, `DROP TABLE` 을 무시해서 V13 이 지운 일곱 테이블이 그대로 남아
있었다. 그래서 데이터 사전 대조(`verify_news.py` 9번)가 "문서에 있는데 스키마에 없다"를
거꾸로 판정했다. 이제 읽는다. **정리 마이그레이션을 미리 반영해 `ALTER … SET SCHEMA` 도 같이 읽는다** —
`collection_run`·`dart_employee_status` 가 `staging` 으로 옮겨가도 파서가 따라간다.

`.gitignore` 는 파일명이 박히는 자리라 옛 이름도 함께 남겼다. 이름이 어긋나는 순간 제외가
조용히 풀려 제3자 기사 제목·URL 이 커밋에 들어간다.

검증: 단위·통합 테스트 59건 통과, `verify_news.py` 실패 0 (9·12번 PASS 로 복귀).

---

## 2. 백엔드에 요청 — 셋

### ① 인덱스 세 개가 V13 으로 넘어오지 않았다

V12 는 `company_news` 에 인덱스 넷을 걸었고, V13 의 `news_article` 에는 하나만 있다.

| V12 | V13 | 무엇에 쓰였나 |
|---|---|---|
| `company_news_url_uk` (UNIQUE, 부분) | **없음** | 같은 기업의 같은 원문 URL 중복 차단 |
| `company_news_latest_idx` | `news_article_lookup_idx` (동일) | 목록 최신순·기간 집계 |
| `company_news_importance_idx` | **없음** | `/news/top` · 중요 이슈 집계 |
| `company_news_category_idx` | **없음** | 카테고리 분포 · 투자·기술 KPI |

**UNIQUE 유실이 제일 급하다.** 지금은 DB 가 중복을 막지 않아, 같은 시드를 두 번 적재하면
같은 기사가 두 행으로 들어간다. 시드 단계 판정(`curate.py`)과 검증 10번은 그대로 두었지만
그건 우리 파이프라인을 통과할 때만 걸린다 — DB 레벨 방어가 아니다.

복원한다면 V12 의 정의를 이름만 바꿔 그대로 쓰면 된다.

```sql
CREATE UNIQUE INDEX news_article_url_uk
    ON news_article (corp_code, original_url) WHERE original_url IS NOT NULL;

CREATE INDEX news_article_importance_idx
    ON news_article (corp_code, importance_score DESC) WHERE importance_score IS NOT NULL;

CREATE INDEX news_article_category_idx
    ON news_article (corp_code, news_category, published_at DESC) WHERE news_category IS NOT NULL;
```

값이 0행이라 지금 넣는 것이 가장 싸다. **정리 마이그레이션에 함께 넣어도 되고 별 번호로
빼도 된다** — 그쪽 판단에 맡긴다.

### ② 컬럼 주석 다섯 개가 넘어오지 않았다

V12 는 여덟 컬럼에 `COMMENT ON COLUMN` 을 달았고 V13 은 넷이다(그중 `id` 는 새로 붙은 것).
넘어오지 않은 것은 `title` · `description` · `published_at` · `related_business` ·
`importance_score` 다.

데이터 사전의 `description` 은 SQL 주석을 먼저 읽으므로, **그동안은 우리 쪽
`build_data_fields.py` 의 DESC 로 V12 문장을 그대로 채워 두었다.** SQL 주석이 복원되면
그쪽이 이긴다 — 우리 쪽을 되돌릴 필요가 없다. 급한 건 아니고 ①과 같이 처리하면 좋겠다.

### ③ `docs/design/db-schema.md` 의 2장 ERD 와 3장 인덱스 표

V13 을 반영하지 않아 mermaid ERD 에 지워진 일곱 테이블이 남아 있고, 3장의
"API ↔ 쿼리 매핑" 이 `company_news_latest_idx` · `company_news_category_idx` 를 가리킨다.
그 문서의 2-1 을 그쪽이 쓰셨고 ERD 원본은 Notion 이라 우리가 손대지 않았다.

---

## 3. 정리 마이그레이션 — 번호가 또 밀렸다

**어제까지 V14 라고 부르던 정리 마이그레이션은 이제 V16 이다.** 인증 기능이
`V14__users.sql` · `V15__email_verification.sql` 을 가져갔다. 그 전에도 V7 → V9 →
V10 → V13 → V14 로 밀렸으니, **번호를 쓰기 전에 `origin/develop` 의 마이그레이션
목록을 먼저 보는 편이 안전하다.** 이 문서도 그래서 아래부터는 번호 대신 "정리
마이그레이션" 이라고 쓴다.

담을 내용은 그대로다 — `dart_financial_account` DROP, `collection_run` ·
`dart_employee_status` 를 `staging` 으로 이동. 준비는 **MR !69** 에 있다
(`pipeline/db.py` 의 `search_path`, `load_raw.py` 의 재무 적재 제거).

**두 이동은 `ALTER TABLE … SET SCHEMA` 로 해주세요.** 새로 만들고 옮겨 담는
방식이면 `search_path` 가 `public` 우선이라 파이프라인이 곧 삭제될 `public` 테이블에
계속 씁니다.

---

## 4. 확인 부탁 — 회신받았다

셋 다 답을 받아 닫는다. 정리된 내용은 5장에 있다.

| 요청 | 회신 |
|---|---|
| 2장 ① 인덱스 복원 | `url_uk` · `importance_idx` 를 정리 마이그레이션에 넣는다. `category_idx` 는 대상이 없어졌다 |
| 2장 ② 컬럼 주석 | 위와 함께 넣는다 (셋) |
| 2장 ③ `db-schema.md` 2·3장 | 백엔드가 맡는다 |

**남은 것은 정리 마이그레이션이 실제로 들어오는지 하나다.** 그때까지 DB 는 URL
중복을 막지 않는다.

---

## 5. V16 · V17 이후 — 요청이 줄었고, 회신도 받았다

이 문서를 쓴 뒤 마이그레이션 둘이 더 들어왔다.

- **V16** `news_article` 의 AI 컬럼 넷(`description` · `news_category` ·
  `related_business` · `analyzed_at`)을 지웠다
- **V17** `guid VARCHAR(500)` 을 더하고 `UNIQUE (corp_code, guid)` 를 걸었다.
  확정 ERD 의 중복 방지 키다

그래서 2장의 요청이 이렇게 정리된다.

| 위 항목 | 지금 |
|---|---|
| ① `news_article_url_uk` (UNIQUE) | **아직 필요하다.** 정리 마이그레이션에 넣기로 회신받았다 |
| ① `news_article_importance_idx` | **아직 필요하다.** 위와 같다 |
| ① `news_article_category_idx` | **불필요.** V16 이 `news_category` 를 지웠다 |
| ① (새로) `guid` 유일성 | **V17 이 넣었다.** 확정 ERD 대로 `UNIQUE (corp_code, guid)` |
| ② 컬럼 주석 | 다섯 → **셋** (`title` · `published_at` · `importance_score`). 정리 마이그레이션 동승 |
| ③ `db-schema.md` 2·3장 | 백엔드가 맡기로 했다 |

`url_uk` 가 들어올 때까지 **DB 는 URL 중복을 막지 않는다.** 시드 생성의 같은 조건
판정이 유일한 방어이고, 표준 문서 6장에도 그렇게 고쳐 적었다.

## 6. 우리 쪽이 따라간 것

파서에 뚫려 있던 구멍 셋을 같은 종류로 보고 함께 막았다. **셋 다 "읽지 않아서 검증이
가짜로 통과" 하는 모양이었다** — 대조가 있으나 마나 한 상태를 만든다.

| 문장 | 안 읽으면 | 회귀 테스트 |
|---|---|---|
| `DROP TABLE` | V13 이 지운 표 일곱이 스키마에 남는다 | `test_지워진_테이블은_스키마에_남지_않는다` |
| `DROP COLUMN` | 사전이 없는 컬럼 넷을 문서화해도 안 잡힌다 | `test_DROP_COLUMN_을_읽는다` |
| `ADD CONSTRAINT … UNIQUE` | 확정 ERD 의 중복 방지 키가 널 허용 컬럼으로 남는다 | `test_ADD_CONSTRAINT_UNIQUE_를_읽는다` |

`SEED_FIELDS` 는 V16 으로 11 → 7 컬럼이 됐다가 V17 의 `guid` 로 8 컬럼이 됐고,
`curate.py` 가 staged 의 `guid` 를 그대로 옮긴다. 데이터 사전도 다시 만들었다.
