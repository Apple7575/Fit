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
거꾸로 판정했다. 이제 읽는다. **V14 를 미리 반영해 `ALTER … SET SCHEMA` 도 같이 읽는다** —
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

값이 0행이라 지금 넣는 것이 가장 싸다. **V14 에 함께 넣어도 되고 별 번호로 빼도 된다** —
그쪽 판단에 맡긴다.

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

## 3. V14 리마인더

이 문서와 별개로 **MR !69** 가 V14 준비를 담고 있다
(`pipeline/db.py` 의 `search_path`, `load_raw.py` 의 재무 적재 제거).

**V14 의 두 이동은 `ALTER TABLE … SET SCHEMA` 로 해주세요.** 새로 만들고 옮겨 담는
방식이면 `search_path` 가 `public` 우선이라 파이프라인이 곧 삭제될 `public` 테이블에
계속 씁니다.

---

## 4. 확인 부탁

1. 2장 ① 인덱스 세 개 — 복원 여부와 번호(V14 동승 vs 별 번호)
2. 2장 ② 컬럼 주석 다섯 개 — ①과 함께 넣을지
3. 2장 ③ `db-schema.md` 2·3장 갱신 — 그쪽에서 맡아주실지
