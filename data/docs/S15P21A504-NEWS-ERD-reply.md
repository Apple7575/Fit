# 뉴스 ERD 마이그레이션(MR !209) 리뷰 회신 — 2판 (2026-09-22)

백엔드 리뷰(2026-09-22, Changes requested)에 대한 데이터 파트 회신이다.
**지적 넷은 저장소 코드로 확인했고 그대로 맞다.** 하나는 우리 적재 경로에는
해당하지 않아 근거를 붙여 적는다. 그리고 **리뷰가 보지 못한 것이 하나 있다.**

- 작성: 데이터 담당 (박세은)
- 관련: [NEWS-LOAD-PIPELINE](S15P21A504-NEWS-LOAD-PIPELINE.md) 5-1·5-2 장 (MR !233)

## 2판에서 바뀐 것

1판 회신에 대한 재회신(부분 UNIQUE 인덱스와 `ON CONFLICT` 추론)을 받아 **지적대로
고쳤다.** 6장을 새로 썼다.

- **부분 인덱스 지적이 맞다** — 조건 없이 `ON CONFLICT` 를 쓰면 적재가 죽는 것을
  실제 PostgreSQL 에서 확인했다
- **적재기가 조건을 붙이도록 고쳤다.** 조건은 사람이 적지 않고 **스키마에서 읽는다**
- **실제 PostgreSQL 재적재 시험을 넣었다** (`tests/news/test_reload_postgres.py`)
- 검사기에 **provider 백필 · provider_url 값 일치 · id 집합 보존** 셋을 더했다
- 그래서 **일반 UNIQUE 제약으로 바꾸실 필요가 없다.** ERD 대로 부분 인덱스를
  유지하셔도 된다 (6장)

---

## 0. 한 장 요약

| # | 지적 | 판정 | 누가 |
|---:|---|---|---|
| 1 | 백필이 들어 있어 기존 데이터를 지울 필요가 없다 | **맞다** | — |
| 2 | 같은 마이그레이션이 `source`·`guid` 를 즉시 지운다 | **맞다** | 백엔드 |
| 3 | AI 뉴스 repository 가 두 컬럼을 직접 조회한다 | **맞다** | AI |
| 4 | `provider_url` 백필이 빠졌다 | **맞다** | 백엔드 |
| 5 | `normalized_url` 에 빈 문자열을 넣으면 안 된다 | **맞다. 다만 우리 적재는 이미 NULL 로 넣는다** | — |
| 6 | (리뷰에 없음) **마이그레이션 번호가 이미 겹쳤다** | 새로 확인 | 백엔드 |
| 7 | (리뷰에 없음) **1차에 키 교체를 넣으면 적재가 멈춘다** | 실측 | 백엔드 |
| 8 | (재회신) 부분 인덱스면 `ON CONFLICT` 가 추론하지 못한다 | **맞다 — 고쳤다** (6장) | — |

**저희가 할 일은 배포 전후 확인뿐이고, 그 검사기를 만들어 두었습니다** (4장).
다만 **3장의 두 가지(번호 재부여 · 1차에서 키 교체 빼기)는 꼭 반영해 주셔야 합니다.**

---

## 1. 확인한 것 — 지적 넷은 그대로 맞다

저장소 실측이다.

**백필**은 V34 2장에 세 문장으로 있다. `source → publisher`,
`guid → provider_article_id`, `provider = 'google_news_rss'`. 기존 500행의 값이
보존되는 것이 맞고, 지우거나 전체 재적재할 이유가 없다.

**즉시 삭제**도 맞다. 같은 파일 4장이 `DROP COLUMN source, guid` 다.

**AI 조회**도 맞다. `ai/news_intelligence/repository.py` 다.

```
116: SELECT id, title, source, published_at, original_url, guid, ...
188: publisher=_normalize_optional_text(row["source"]),
191: guid=_normalize_optional_text(row["guid"]),
```

**`provider_url` 백필 누락**도 맞다. V34 에 `provider_url` 을 채우는 문장이 없다.

주신 UPDATE 문의 전제 — "현재 적재된 `original_url` 은 전부 Google 뉴스 링크" — 도
맞다. `data/manifests/seed/news_article.json` 이 `url_google_news_rows: 500` ·
`url_publisher_rows: 0` 이다.

> **다만 이 전제는 지금 500행에만 성립한다.** 수집기는 언론사 원문 주소를 얻으면
> `original_url` 에 그것을 넣고 구글 링크는 `provider_url` 로 보낸다
> (`pipeline/news/curate.py`). 전 종목으로 넓히면 `url_publisher_rows > 0` 인 행이
> 생긴다. **같은 SQL 을 그때 다시 쓰면 안 된다** — 한 번 쓰고 닫는 문장으로 봐 주시면
> 된다.

---

## 2. 5번 — 지적은 맞지만 우리 적재 경로에는 해당하지 않는다

**빈 문자열이 위험하다는 것은 실측으로 확인했다.** 임시 DB 에 마이그레이션을 얹고
같은 기업 두 행에 `normalized_url = ''` 를 넣어 봤다.

```
ERROR:  duplicate key value violates unique constraint "news_article_normalized_url_uk"
DETAIL:  Key (corp_code, normalized_url)=(00000001, ) already exists.
```

지적하신 그대로다. **그런데 우리 적재기는 빈 문자열을 넣지 않는다.** 시드 CSV 는
빈 칸으로 내보내지만, 적재기가 읽을 때 빈 문자열을 NULL 로 바꾼다.

```python
# scripts/load_seed_csv.py:122
return [{k: (v if v != "" else None) for k, v in row.items()} ...]
```

그래서 `normalized_url` 과 `body_text` 는 **NULL 로 들어간다.** 두 컬럼을 NULL 로
두는 판단에도 동의한다 — 구글 링크를 원문 주소로 푸는 세 방법이 2026-09-21 실측에서
모두 실패했고(오프라인 해독 500/500 실패 · 리다이렉트 추적은 본문 0바이트 · 구글
내부 API 는 서명 필요), 본문 저장은 근거가 없다(`news-poc/90-source-review.md`).

혹시 모르니 **검사기 6번**이 배포 뒤 빈 문자열 행수를 직접 센다.

---

## 3. 리뷰가 보지 못한 것 — 번호가 이미 겹쳤다

정적 검토라 놓치신 것 같다. **`V34` 는 develop 이 이미 가져갔다.**

| 어디 | 파일 |
|---|---|
| `origin/develop` (머지됨) | `V34__rag_embedding_half_precision.sql` |
| MR !209 브랜치 | `V34__news_article_provider_columns.sql` |

!209 는 임베딩 float16 이 들어오기 **전에** 갈라져 나와서(분기점 `55cbbc6`)
브랜치 안에서는 보이지 않는다. `application.properties` 에 중복을 넘기는 설정이
없어 **이대로 머지되면 Flyway 가 시작하지 않는다.**

**그리고 제안하신 대로 마이그레이션을 둘로 쪼개면 번호가 두 개 필요하다.**
2026-09-22 기준 원격 전 브랜치를 훑어 `V35` 이상을 쓰는 곳이 없으므로 **V35 · V36**
이 비어 있다. 예를 들면 이렇게 된다.

```
V35__news_article_provider_columns.sql   1차 — 컬럼 추가 + 백필(provider_url 포함)
                                                **키 교체는 넣지 않는다** (아래 실측)
   … AI 를 신규 컬럼 기준으로 전환하고 검증 …
V36__news_article_drop_source_guid.sql   후속 — 키 교체 + source·guid 삭제
```

같은 사고가 또 나지 않도록 **우리 파서가 중복 번호에서 멈추게 했다** (MR !234).
시드 생성·적재·검증이 모두 지나는 `flyway.load` 가 겹친 번호와 파일 이름을 적고
죽는다. 두 MR 은 !233 → !234 순서로 머지해야 한다.

### ⚠️ 쪼갤 때 **키 교체를 1차에 넣으면 적재가 멈춘다** — 실측

쪼개는 방식에 따라 결과가 갈린다. 두 경우를 다 돌려 봤다.

| 1차의 내용 | 적재기가 고르는 자연키 | 결과 |
|---|---|---|
| 컬럼 추가 + 백필만 (guid UK 유지) | `(corp_code, guid)` | **정상** |
| 컬럼 추가 + 백필 + **키 교체** (guid 컬럼은 남김) | `(corp_code, guid)` | **적재 실패** |

두 번째가 위험한 이유는 이렇다. 적재기는 자연키를 **컬럼이 있는지**로 고르는데
(`load_seed_csv.natural_key`), `guid` 컬럼은 1차에서도 남아 있으므로 여전히
`(corp_code, guid)` 를 고른다. 그런데 그 유일 제약은 이미 없다. 실제 DB 에서:

```
INSERT INTO news_article (...) VALUES (...)
ON CONFLICT (corp_code, guid) DO UPDATE SET title = EXCLUDED.title;

ERROR:  there is no unique or exclusion constraint matching the ON CONFLICT specification
```

**우리 사전 검사도 이것을 못 잡는다.** 스키마를 읽는 파서가 `DROP CONSTRAINT` 를
처리하지 않아, 없어진 `(corp_code, guid)` 키가 살아 있는 것으로 보인다 — 검사는
초록인데 실제 적재만 죽는다. 파서 쪽은 저희가 따로 고치겠다.

**그래서 부탁드린다: 1차는 컬럼 추가와 백필까지만 두고, 키 교체(제약 삭제 + 부분
UNIQUE 인덱스 둘)는 `source`·`guid` 삭제와 함께 후속 마이그레이션에 넣어 주세요.**
그러면 전환기 내내 적재기가 기존 키로 정상 동작하고, 후속이 들어오는 순간
`provider_article_id` 기준으로 갈아탄다(MR !222 로 양쪽 스키마에서 돈다).

---

## 4. 배포 전후 확인 — 검사기를 만들어 두었습니다

주신 6항목을 기계로 돌린다. `scripts/verify_news_erd_migration.py` 다.

```bash
python scripts/verify_news_erd_migration.py --snapshot _out/news_before.json   # 배포 전
python scripts/verify_news_erd_migration.py --compare  _out/news_before.json   # 배포 후
python scripts/verify_news_erd_migration.py --code-only                        # DB 없이 7번만
```

**배포 전에 반드시 먼저 찍어야 한다.** `source`·`guid` 는 마이그레이션이 지우므로,
값이 어디로 갔는지는 지운 뒤에 DB 만 봐서는 알 수 없다. 스냅샷이 행마다
`id → source·guid` 를 들고 있다가 배포 뒤에 한 행씩 맞춰 본다.

| # | 검사 | 주신 항목 |
|---:|---|---|
| 1 | 전체 행 수가 같다 | 마이그레이션 전후 전체 행 수 동일 |
| 2 | `source` 가 있던 행은 모두 `publisher` 로 (행 단위) | source → publisher 이동 |
| 3 | `guid` 가 있던 행은 모두 `provider_article_id` 로 (행 단위) | guid → provider_article_id 이동 |
| 4 | 새 자연키 중복 없음 (제공처 기준 · 원문 URL 기준) | 신규 자연키 중복 없음 |
| 5 | 기존 Google 행의 `provider_url` 이 `original_url` 과 **값까지** 같다 | provider_url 백필 여부 · **값 일치**(2판) |
| 6 | `normalized_url` 에 빈 문자열이 없다 | (2장의 지적) |
| 7 | AI 코드가 `source`·`guid` 를 조회하지 않는다 | AI 조회 여부 |
| 8 | `provider` 가 모든 행에 채워졌다 | **provider 백필**(2판) |
| 9 | **id 집합이 보존됐다** | **ID 집합 보존**(2판) |

9번을 따로 둔 이유가 있다. **행 수만 보면 지워지고 새로 들어간 것을 놓친다.**
일부러 한 행을 지우고 다른 행을 넣어 보면 1번은 초록인데 9번만 빨개진다 —
"없어진 id 1개 · 새로 생긴 id 1개" 로 잡힌다.

7번만 DB 없이 돈다. 지금 돌리면 이렇게 나온다 — **아직 빨간 것이 맞다.**

```
✖ [7] AI 코드가 source·guid 를 조회하지 않는다
      ! repository.py:116: SELECT id, title, source, published_at, original_url, guid,
      ! repository.py:188: publisher=_normalize_optional_text(row["source"]),
      ! repository.py:191: guid=_normalize_optional_text(row["guid"]),
```

### 검사기 자체를 어떻게 검증했나

임시 postgres 에 V1~V34 를 전부 얹고 표본 4행을 넣은 뒤, **실제 !209 SQL 과 주신
백필 UPDATE 를 그대로 적용**해 전 항목이 통과하는 것을 봤다. 그다음 일부러 망가뜨려
**전부 다시 빨개지는 것**까지 확인했다 — 행 삭제 · publisher 훼손 · provider_url
되돌리기와 **엉뚱한 값 넣기** · 빈 문자열 · 자연키 중복 · provider 비우기 ·
**행을 지우고 새로 넣어 id 만 바꾸기**. 통과만 보고 믿지 않기 위한 절차다.

---

## 5. 정리 — 남은 순서

1. **번호를 V35(+V36)로 다시 매긴다** — 백엔드
2. **1차 마이그레이션**: 컬럼 추가 + 백필(`provider_url` 포함). **키 교체는 넣지 않는다** — 백엔드
3. 배포 **전** 스냅샷 — 데이터
4. **AI 를 신규 컬럼으로 전환** — AI
5. 배포 **후** 대조(검사기 9항목 전부 초록) — 데이터
6. **후속 마이그레이션**: 키 교체 + `source`·`guid` 삭제 — 백엔드
7. 후속 배포 뒤 한 번 더 대조 — 데이터

3번은 **V35 배포 직전**에 찍겠습니다. 날짜·시각을 알려 주시면 맞추겠습니다.

---

## 6. 부분 UNIQUE 인덱스와 `ON CONFLICT` — 지적대로 고쳤습니다 (2판)

### 지적이 맞다

실제 PostgreSQL 에서 확인했다. 부분 인덱스는 **같은 조건을 conflict_target 에
적어야** 중재자로 쓰인다.

```sql
CREATE UNIQUE INDEX t_uk ON t (corp_code, provider, provider_article_id)
    WHERE provider_article_id IS NOT NULL;

-- 조건 없이
INSERT ... ON CONFLICT (corp_code, provider, provider_article_id) DO UPDATE ...
ERROR:  there is no unique or exclusion constraint matching the ON CONFLICT specification

-- 조건을 붙여서
INSERT ... ON CONFLICT (corp_code, provider, provider_article_id)
             WHERE provider_article_id IS NOT NULL DO UPDATE ...
INSERT 0 1
```

### 고친 것 — 조건은 사람이 적지 않고 스키마에서 읽는다

| 어디 | 무엇 |
|---|---|
| `pipeline/news/flyway.py` | `CREATE UNIQUE INDEX` 의 `WHERE` 절을 읽어 키 묶음과 함께 남긴다. 예전에는 **버리고 있었다** |
| `scripts/load_seed_csv.py` | `conflict_predicate()` 가 그 조건을 꺼내 적재기에 넘긴다 |
| `pipeline/db.py` | `upsert(..., conflict_where=...)` 가 `ON CONFLICT (키) WHERE 조건` 을 만든다 |

조건문을 코드에 박지 않은 것이 요점이다. **마이그레이션의 `WHERE` 가 바뀌면 적재기가
따라간다.** 사람이 양쪽을 맞추는 일이 없다. 조건은 스키마에서 읽은 것만 넘기고
사용자 입력은 넣지 않는다.

### 그래서 일반 UNIQUE 제약으로 바꾸실 필요가 없습니다

적재기가 부분 인덱스를 다루므로 **ERD 대로 부분 인덱스를 유지하셔도 된다.**
어느 쪽을 고르셔도 적재기는 돈다 — 일반 제약이면 조건이 비어 예전과 같은 문장이
나간다.

### 실제 PostgreSQL 재적재 시험

`tests/news/test_reload_postgres.py` 다. 넷이고, `CA_TEST_DATABASE_URL` 이 없으면
건너뛴다.

| 시험 | 무엇을 고정하나 |
|---|---|
| 조건 없이 넣으면 죽는다 | 회귀의 모양을 박아 둔다 |
| 조건을 붙이면 두 번 넣어도 같다 | 두 번째는 전부 갱신이고 행 수가 늘지 않는다 |
| 마이그레이션 전 스키마에서는 조건 없이 돈다 | 전환 전 경로가 그대로인지 |
| 적재기가 스키마에서 같은 조건을 읽어 온다 | 조건이 코드가 아니라 스키마에서 온다 |

돌리는 법 — 임시 컨테이너면 충분하다.

```bash
docker run -d --name ca-check-pg -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=company_analysis postgres:18
CA_TEST_DATABASE_URL="postgresql://postgres:pw@localhost:5432/company_analysis" \
  python -m unittest discover -s tests/news -t .
```

실측: 넷 다 통과했고, `CA_TEST_DATABASE_URL` 없이 돌리면 넷 다 건너뛴다.
뉴스 시험 전체는 105건 통과다.
