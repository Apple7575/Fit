# 작업 이어받기 (HANDOFF)

> 마지막 갱신: 2026-09-02 / 티켓: **S15P21A504-84** (기업 기본·재무·직원 5개년 데이터 확보)
> 브랜치: `feature/S15P21A504-84-dart-confirmed-data-collection`
> **이 문서만 읽고 바로 이어서 작업할 수 있게** 쓴 것이다.
>
> **86 반영 (2026-09-02).** 검증 티켓 **S15P21A504-86**(DART 확정 데이터 누락·정합성 검증)이
> 끝나 검증 스크립트 5개 · `known_findings.yaml` · API 응답 원본이 추가됐다.
> 지시서는 `docs/S15P21A504-86.md`, 실행은 `scripts/verify_all.py` 하나로 묶여 있다.

---

## 1. 한 줄 요약

**DART 수집 → 정규화 → develop 스키마 적재 → 원천 대조까지 끝났다.**

타깃 10개사 × 2021~2025년 지표 6종이 근거와 함께 PostgreSQL에 들어가 있고, 재실행해도 값이 변하지 않는다. 백엔드 조회 API가 읽는 `company_metric`에 326행이 있다.

**86에서 API 노출값 대조까지 닫았다.** 원천 ↔ DB ↔ API 3자 대조가 전부 통과해 F-30이 완료됐고, 검증은 `python scripts/verify_all.py` 하나로 돈다 (3장 5단계).

**닫힌 것은 `company_metric` 한 갈래다.** 지표 시계열·사업부별 숫자·투자/M&A·뉴스는 아직 스키마에 없어 검증 대상 자체가 없다. "3자 대조 완결"은 **현재 스키마 기준**이라는 뜻으로 읽어라.

---

## 2. 지금 뭐가 있나

### 파일

```
data/
├── .env                    DART 인증키 + DATABASE_URL   커밋 금지
├── .env.example            견본
├── .venv/                  가상환경 (uv 로 재생성 가능, 커밋 안 함)
├── config/
│   ├── patterns.yaml           계정명·라벨·정규식·임계값. 이름으로 찾는 규칙 전부
│   ├── targets.csv             적재 대상 10개사
│   ├── targets_baseline.csv    회귀 기준선 10개사 (targets 와 3곳 다르다)
│   ├── company_universe.csv    상장사 3,930건
│   ├── ksic_division.csv       KSIC 중분류 77건
│   └── known_findings.yaml     확인을 마친 정합성 발견 기준선 (86). 등록 기준이 주석에 있다
├── docs/
│   ├── S15P21A504-84.md        작업 지시서. 확정 결정 D-1~D-3 이 여기 있다
│   ├── S15P21A504-86.md        검증 티켓 지시서 (86). Step 0~5 와 완료 판정
│   ├── DESIGN.md               ★ 설계·파싱 규칙·정규식·임계값. 4장이 핵심
│   ├── API_NOTES.md            API 실측 기록. 함정 3개
│   ├── HANDOFF.md              이 문서
│   ├── WORK_PLAN.md            브랜치 38 시절 WP-1~12 (과거 기록)
│   ├── BACKLOG_STATUS.md       티켓별 AC 충족 근거
│   └── COMPARISON_RULES.md     동종업계 비교 규칙
├── pipeline/               수집·정규화·DB 접근
│   └── normalize/              revenue · employee · rnd · runner
├── scripts/                CLI 13개 (아래 3장). 검증 5개는 verify_all.py 로 묶여 있다
├── tests/fixtures/normalize/   회귀 기준선 150건
├── tests/fixtures/api/         백엔드 API 응답 원본 23건 (86). verify_api.py 가 읽는다
├── .cache/                 API 원본 310파일 305MB   커밋 안 함
├── _log/                   실행 로그                커밋 안 함
└── _out/                   커버리지 리포트          커밋 안 함
```

**`.cache/` 가 가장 중요한 실행 자산이다.** 이게 있으면 API 호출 없이 정규화·적재를 반복할 수 있다. 지워도 재수집 가능하지만 310콜이 든다.

### DB (`dart-data-pg-local`, 포트 55432)

```
industry                    77행   KSIC 중분류
company                  3,930행   상장사 명부 (지표는 없다. 이름·업종만)
metric                       7행   지표 카탈로그 (활성 6 + rd_cost 비활성 1)
dart_financial_account   1,647행   DART 주요계정 원본
dart_employee_status       217행   DART 직원현황 원본
company_metric             326행   ★ 백엔드 조회 API 가 읽는 테이블
metric_evidence            329행   지표별 근거·판정
collection_run               4행   실행 이력
```

### 마이그레이션

**`V5__add_metric_evidence.sql`을 이번에 추가했다** — `metric_evidence` 테이블 + `metric`에 `rd_cost` 1행(`is_active=FALSE`).

`V1`~`V4`는 백엔드 소유다. develop 현재 상태는 이렇다.

```
V1__init_schema.sql                    초기 스키마
V2__seed_metric.sql                    지표 6종 시드
V3__industry_ksic_division.sql         industry 77건 시드 + company.induty_code 컬럼 추가
V4__rename_average_metric_codes.sql    avg_salary→average_salary, avg_tenure→average_tenure
V5__add_metric_evidence.sql            ← 이번 티켓
```

**처음엔 `V3`으로 썼다가 `V5`로 바꿨다.** 작업 중 develop에 `V3`·`V4`가 먼저 들어가 번호가 겹쳤다. Flyway는 파일명이 아니라 **버전 번호로 식별**하므로 3번이 둘이면 `Found more than one migration with version 3`으로 기동에 실패한다. **git 머지에서는 충돌이 나지 않는다** — 파일명이 달라 깨끗하게 붙고, 앱을 띄울 때 터진다.

`V3`이 추가한 `company.induty_code`(DART 5자리 세분류)는 주석에 "적재 파이프라인이 두 코드를 함께 채운다"고 명시되어 있어 `load_company.py`가 채운다.

`industry` 77건은 **`V3`이 시드한다.** `load_company.py`는 적재하지 않고 `config/ksic_division.csv`와 일치하는지 **대조만** 한다 — 원천이 같은데 두 곳에서 넣으면 한쪽만 바뀌었을 때 알아챌 수 없다.

---

## 3. 처음부터 재현하기

### 0단계. 환경 (30분)

```powershell
# Python — 시스템 PATH 의 python 은 Microsoft Store 스텁이라 안 된다
uv python install 3.12
cd C:\Users\SSAFY\Desktop\S15P21A504\data
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt

# 인증키 — .env.example 을 .env 로 복사하고 DART_API_KEY 를 채운다
#   https://opendart.fss.or.kr → 인증키 신청/관리 (40자)
```

**`DATABASE_URL` 의 호스트는 반드시 `127.0.0.1`.** `localhost`로 쓰면 psycopg가 IPv6(`::1`)를 먼저 시도하는데 컨테이너가 IPv4에만 바인딩되어 있어 **무한 대기한다**(실측: 127.0.0.1 0.1초 vs localhost 45초 타임아웃까지 무응답). `connect_timeout`을 주지 않아 폴백하지도 않는다.

### 1단계. DB 컨테이너

팀 공용 `infra/`는 건드리지 않는다. 별도 컨테이너를 쓴다.

```powershell
docker run -d --name dart-data-pg-local -p 127.0.0.1:55432:5432 `
  -e POSTGRES_DB=company_analysis -e POSTGRES_USER=ssafy -e POSTGRES_PASSWORD=<비밀번호> `
  -e "POSTGRES_INITDB_ARGS=--locale-provider=icu --icu-locale=ko-KR --encoding=UTF8" `
  -e TZ=Asia/Seoul postgres:18
```

로케일을 팀 `infra/docker-compose.yml`과 맞춘 것이다. 다르면 한글 정렬이 팀 DB와 달라진다.

마이그레이션 적용 — **백엔드를 띄울 계획이면 이 절을 건너뛰고 백엔드가 하게 두라.**

> **경고 (86에서 겪음).** 아래처럼 `psql`로 직접 적용하면 테이블은 만들어지지만
> **Flyway의 이력 테이블(`flyway_schema_history`)이 생기지 않는다.** 그 DB에
> 백엔드를 띄우면 이렇게 거부하며 기동에 실패한다.
>
> ```
> Found non-empty schema(s) "public" but no schema history table.
> ```
>
> Flyway 입장에서는 "테이블은 있는데 누가 뭘 했는지 모르겠다"라 안전하게 멈추는
> 것이다. **DATA만 쓸 때만** 아래를 쓰고, API 대조처럼 백엔드가 필요해지면
> DB를 새로 만들어 백엔드가 마이그레이션하게 하라.

DATA 스크립트만 돌릴 때 (백엔드를 띄우지 않을 때):

```bash
cd backend/src/main/resources/db/migration
for f in $(ls V*.sql | sort -V); do
  docker exec -i dart-data-pg-local psql -U ssafy -d company_analysis -v ON_ERROR_STOP=1 -q < "$f"
done
```

### 2단계. 수집 (30초, 310콜)

```bash
cd data
python scripts/collect.py --targets config/targets_baseline.csv   # 회귀용 10개사 250콜
python scripts/collect.py --profile                                # 기업개황 10콜
python scripts/collect.py --profile --targets config/targets_baseline.csv   # 기업개황 3콜
python scripts/collect.py                                          # 적재용 10개사  60콜
```

캐시에 있으면 호출하지 않는다. 실패가 있으면 `_log/failed_<run_id>.csv`가 생기고 `--retry <파일>`로 그 건만 다시 돈다.

### 3단계. 회귀 검증 — 여기서 깨지면 아래로 넘어가지 마라

```bash
python scripts/verify_normalize.py
# 기대: 매출 50/50 · R&D 50/50 · 직원 50/50, "통과"
```

깨지면 **원본 캐시가 없어서인지 코드가 깨진 건지 먼저 구분하라.** 캐시가 비어 있으면 전부 `RawMissing`으로 실패한다.

### 4단계. 적재 — 순서가 강제된다

```bash
python scripts/load_company.py     # industry 77 → company 3,930  (FK 때문에 이게 먼저)
python scripts/load_raw.py         # 착지 테이블 1,647 + 217
python scripts/load_metrics.py     # company_metric 326 + metric_evidence 329 + collection_run
```

전부 `--dry-run`이 있다. `load_metrics.py`는 `--corp` / `--years` / `--retry`로 대상을 좁힐 수 있다.

### 5단계. 검증

```bash
python scripts/verify_all.py
# 기대: [1]~[4] 전부 통과, 종료코드 0
```

**적재를 마치면 이걸 돌린다.** 검증이 다섯 갈래로 흩어져 있어 하나씩 기억해야 했던 것을 묶은 것이다. **종료코드로 성공·실패를 알리므로** 사람이 출력을 다 읽지 않아도 판단할 수 있다.

```
[1] 정규화 회귀   verify_normalize.py   기준선 150건        DB·API 불필요
[2] 원천 → DB     verify_db.py          329/329 · 139/139   DB 필요
[3] 원천 정합성   verify_source.py      검산 6축             DB 필요
[4] DB → API      verify_api.py         3,449건             DB + 응답 원본 필요
                                        지표·상세·검색·비교 4종.
                                        시계열은 응답만 저장하고 아직 대조하지 않는다
[5] 누락 사유     report_gaps.py        사유 격자            판정하지 않는다
```

앞이 실패해도 뒤를 건너뛰지 않는다 — 어디까지 되는지 알아야 원인을 좁힐 수 있다.

[4]는 API를 호출하지 않고 받아둔 `tests/fixtures/api/`를 읽는다. 응답이 오래됐으면 `python scripts/probe_backend_api.py`로 먼저 다시 받아라 (백엔드가 떠 있어야 한다). 백엔드를 못 띄우는 환경에서는 `--skip-api`로 [1]~[3]만 돌린다.

낱개로 돌릴 수도 있다.

```bash
python scripts/verify_db.py --report
# 기대: 전 항목 0건, "통과". _out/coverage.csv 생성
```

---

## 4. 확정된 결정 (뒤집지 마라)

지시서(`docs/S15P21A504-84.md`)의 D-1~D-3에 더해, 이번 작업에서 확정한 것들이다.

| # | 결정 | 근거 |
|---|---|---|
| **D-1** | 파이프라인이 DB에 직접 upsert. 백엔드는 읽기만 | 확정 데이터는 연 1회 갱신 · 8.3MB XML 파싱은 요청 시간 내 불가 |
| **D-2** | develop의 Flyway 스키마 기준. `company_year`(wide)는 버리고 `company_metric`(long)에 넣는다 | 백엔드 조회 API가 이미 이 테이블을 읽는다 |
| **D-3** | 이번 범위는 84만. 85·86은 손대지 않는다 | — |
| **A** | R&D 금액은 `metric`에 `rd_cost`를 `is_active=FALSE`로 추가해 착지시킨다 | 조회 경로 6개 전수 확인 결과 API에 노출되지 않는다 |
| **B** | `metric_code`를 develop 카탈로그 값으로 개명. `runner.py`에서 바꾼다. **V4 반영: `average_salary`·`average_tenure`** | FK가 `metric`을 참조하므로 내부 이름은 적재가 거부된다(실측 확인). CSV와 DB가 같은 이름을 갖게 하려면 한 곳에서 바꿔야 한다 |
| **C** | `company.corp_name`에 **종목명**을 넣는다. 타깃 10개사는 `targets.csv`의 `display_name`으로 덮어쓴다 | 등록명을 넣으면 `SK하이닉스`·`NHN`으로 검색이 안 된다 |
| **D** | `company.listed_date`는 채우지 않는다. 커버리지 판정은 `targets.csv`의 `listed_from`으로 한다 | **확인 완료(2026-09-02): 기업개황 응답에 상장일 필드가 아예 없다.** KRX 등 다른 소스가 필요하다 |

**결정 B 주의**: `runner.py`의 `Evidence`로 나가는 `metric_code` 문자열만 바꿨다. **dataclass 필드명(`avg_salary_krw` 등)은 그대로 두었다** — 회귀 기준선이 그 이름에 묶여 있다. 개명 후 회귀 150/150을 다시 확인했다.

---

## 5. 검증 수치 (실측)

| 검사 | 결과 |
|---|---|
| 정규화 회귀 (기준선 150건) | **150/150 통과** · 매출 `verified` 50 · R&D `high` 50 · 직원 경고 0 |
| 수집 | 310콜 · 실패 0 · 30초 · 13개사 62 기업-연도 |
| `industry`·`company` 재실행 | 3회 실행에 77 / 3,930행 불변 |
| `company_metric` 재실행 | 2회 실행에 행 수·값 불변 (MD5 지문 동일) |
| 원천 → DB (정규화 재실행 대조) | **329/329 일치** |
| 독립 대조 (정규화 코드 미사용) | **139/139 일치** |
| 참조 무결성 | FK 고아 0 · 근거 없는 값 0 |
| DB → API 노출값 (86) | **3,449건 전수 통과** · 응답 23건(엔드포인트 5종) 중 **19건 대조**(지표 9 · 상세 3 · 검색 5 · 비교 2) |
| 시계열 응답 (86) | 4건 저장 · **대조 미실시** — 연도 채움 · 빈 구간 필터 · `rd-ratio` 키 정규화가 자바 코드에만 있어 별도 대조가 필요하다 (후속 티켓) |
| 원천 정합성 검산 (86) | 검산 6축 · 새 모순 **0건** · 차이 3건(기록 대상) · 검산 가능 범위 **47/47** |

### 커버리지 — 분모 기준을 반드시 같이 읽어라

```
기업 10 × 연도 5 = 50건
  − 상장 이전 3건 제외  →  대상 47건
    (시프트업 2021~2023 — 2024 상장. 사업보고서가 존재하지 않는다. "수집 실패"가 아니다)
```

| 지표 | 확보 | 확보율 | verified | unverified | rejected |
|---|---|---|---|---|---|
| `revenue` | 47/47 | 100% | 47 | 0 | 0 |
| `operating_profit` | 47/47 | 100% | 0 | 47 | 0 |
| `employee_count` | 47/47 | 100% | 14 | 33 | 0 |
| `average_salary` | 47/47 | 100% | 46 | 1 | 0 |
| `average_tenure` | 47/47 | 100% | 13 | 34 | 0 |
| `rd_ratio` | 46/47 | 97.9% | 45 | 1 | 1 |
| `rd_cost` | 45/47 | 95.7% | 45 | 1 | 1 |

**`unverified`가 많은 건 값이 틀렸다는 뜻이 아니다.** 확인할 방법이 없다는 뜻이다.
- `operating_profit`은 대조할 두 번째 경로가 없어 **구조적으로 절대 `verified`가 되지 않는다**
- 직원 지표는 회사가 합계 행을 안 적으면 대조 상대가 없다 (62건 중 48건이 합계 행 없음)

### 샘플 값 (실제와 대조 완료)

```
삼성전자 2025  매출 333.6조 · 영업이익 43.6조 · R&D 37.75조(11.3%)
              128,881명 · 근속 13.72년 · 급여 1.57억
```

`rd_ratio`가 11.32(우리 계산)가 아니라 **11.30(회사 보고값)** 이다. `runner.py`가 `ratio_reported`를 우선한다. 의도된 동작이다.

---

## 6. 미해결 / 넘겨야 할 것

### 6-1. 백엔드에 알려야 할 것

인계 문서를 만들어 뒀다 → **https://claude.ai/code/artifact/1861c70a-166e-48eb-bed7-6d595f47b71d**

| # | 항목 | 상태 |
|---|---|---|
| 1 | `company.corp_name`에 등록명이 아니라 종목명이 들어갔다. **V1의 `COMMENT`와 어긋난다** | 주석 정정은 백엔드 V4 소관 |
| 2 | `ceo_nm`·`established_date`·`corp_name_eng` — **타깃 13개사 채움 완료**(백엔드 답변: 타깃만). 나머지 3,917행은 NULL 유지 | 해결됨 |
| 2-1 | `listed_date` — **기업개황 응답에 상장일 필드가 없음을 실측 확인.** KRX 등 다른 소스 필요 | 백엔드 공유 완료 |
| 2-2 | `dart_modify_date` — 기업개황이 아니라 corpCode.xml 에 있다. 아직 안 채움 | 필요 시 |
| 3 | `Metric.java` 주석 "V2 시드의 6행이 전부다"가 낡았다 (이제 7행) | 동작 영향 없음 |
| 4 | `findAll()`을 쓰면 비활성 `rd_cost`까지 나온다 | 현재 호출부 0곳. `findByActiveTrue…`를 쓸 것 |
| 5 | `ddl-auto=validate` 유지 필수 | `update`로 바뀌면 적재 데이터가 위험하다 |

### 6-2. 스키마 변경이 필요해 못 한 것 (ALTER 금지라 보고만 함)

**`dart_financial_account`에 전체재무제표(`fnlttSinglAcntAll`)를 넣지 못했다.**

UNIQUE 키가 `(corp_code, bsns_year, reprt_code, fs_div, sj_div, account_nm)`인데 전체재무제표는 이 키로 행이 구분되지 않는다.

```
주요계정      1,765행 → 고유키 1,647   값이 다른 중복      0건   안전
전체재무제표  23,225행 → 고유키 15,897   값이 다른 중복  1,520건   손실
```

같은 계정명이 `account_id`·`account_detail`로만 갈린다(삼성전자 2025 자본변동표 `기초자본` 7행이 전부 다른 값). 넣으면 1행만 남고 나머지가 조용히 사라진다.

**부작용**: 이 테이블만으로는 매출 정규화의 **경로 B·C(전체재무제표 기반)를 재현할 수 없다.** 경로 A(주요계정)만 가능하다. 경로 B·C 재처리는 계속 `.cache/`가 필요하다.

해결하려면 `account_id`·`account_detail` 컬럼 추가(V4)가 필요하다.

### 6-3. 원천 데이터 오류 (→ 86 이관)

**엔씨소프트 2024 직원현황에서 `연구개발/남`이 두 번 나온다.** 두 번째 행(840명)은 성별이 `여`여야 한다. 합계 행으로 검산하면 명백하다.

```
남 상세 합  104 + 505 + 1,968 = 2,577  = 성별합계 남 2,577  ✓
여 상세 합   49 + 366 +   840 = 1,255  = 성별합계 여 1,255  ✓
```

DART가 준 값 자체가 틀렸다. **고치지 않았다** — 회사명 분기 금지이고 값을 임의로 바꾸는 건 더 나쁘다. UNIQUE 키로 구분할 수 없어 뒤 행이 착지 테이블에서 빠졌고, 적재 로그에 명시된다.

**지표 값에는 영향이 없다.** 정규화는 캐시를 직접 읽고 상세 행을 전부 더하므로 3,832명이 정확히 나온다. 어긋나는 건 착지 테이블 합계뿐이고 자체 검증에서 정확히 −840으로 잡힌다.

**86 반영.** `config/known_findings.yaml`에 `ncsoft-2024-emp-duplicate`로 등록했다. **실패로 세지 않되 실행할 때마다 계속 출력된다** — 늘 빨간불인 검사는 사람이 무시하게 되고, 그러면 새로 생긴 문제도 함께 묻힌다. 같은 유형이 더 있는지는 C축(착지 ↔ 지표)으로 47건 전수 검사했고, 모순은 이 1건뿐이었다.

### 6-4. 파서 미해결 (DESIGN 8장, 브랜치 38부터 이어짐)

| # | 항목 | 영향 |
|---|---|---|
| 1 | 시프트업 2024 R&D 금액 행 라벨이 `합계` 단독 | `rd_cost` 값 없음 (비율 12.75는 있음) |
| 2 | 시프트업 2025 문서에 4,937행 병합 표 (마크업 파손) | `rd_cost`·`rd_ratio` `rejected` |
| 3 | 다른 업종 미검증 | 지금은 KSIC 26·29·58·63. 제약(21)·금융(64·66) 미검증 |

`patterns.yaml`에 `amount_row_fallback_re`·`candidate_table_max_rows`가 준비되어 있다.

### 6-5. 아직 안 한 것 (86에서 해소된 것은 그 자리에 표시했다)

- **커버리지 검증 범위가 좁다** → **86에서 해소.** 합계 행이 없어도 걸리는 축(급여 교차 · 착지↔지표 · 자릿수 급변 · R&D 역산)을 더해 검산 가능 범위를 **14/47(30%) → 47/47(100%)** 로 올렸다 (`scripts/verify_source.py`). 단 **검산이 100%가 됐다고 데이터가 100% 맞다는 뜻은 아니다** — 검산은 같은 사실을 두 군데서 말한 것끼리 맞춰보는 것이라, 회사가 한 번만 말한 값은 여전히 확인할 수 없다. 늘어난 것은 틀렸을 때 알아챌 수 있는 범위다.
- **`company` 3,930건 중 타깃 10개사 외에는 이름을 검수하지 않았다.** `NAVER`처럼 종목명이 영문이고 등록명이 한글인 케이스가 66건 있다(`NAVER → 네이버(주)`). 한글로 검색하면 안 걸린다.
- **API 노출값 대조**(F-30 AC의 3자 대조 중 세 번째) → **86에서 완료.** 로컬에 백엔드를 띄워 응답 원본을 받고 DB와 기계적으로 대조했다 (3,449건 전수 통과, `scripts/verify_api.py`). F-30은 닫혔다 — 단 **현재 스키마(`company_metric`) 기준**이다.
- **시계열 응답은 대조하지 않았다.** `probe_backend_api.py` 가 4건을 저장하지만 `verify_api.py` 에 `timeseries_` 를 읽는 코드가 없다. **DB만 봐서는 알 수 없는 것이 여기 모여 있다** — 요청 구간의 모든 연도를 채우고 없는 해를 `null` 로 두는 처리, 구간에 값이 하나도 없을 때 `fiscal_year` 가 `null` 인 행 하나로 오는 것을 걸러내는 처리, `rd-ratio` → `rd_ratio` 키 정규화. 셋 다 SQL 이 아니라 `CompanyMetricService` 자바 코드에 있다. `check_metrics` 의 `scaled()` 를 그대로 재사용하면 된다. **후속 티켓.**
- **스테이징 DB에는 데이터가 없다.** 이번 검증은 로컬 백엔드 기준이다. 스테이징에 적재한 뒤에는 같은 스크립트를 그대로 쓰되 **접속 대상을 두 군데서 바꿔야 한다** — `.env`의 `DATABASE_URL`(DB)과 `probe_backend_api.py --base-url`(API 응답 재수집). `verify_all.py` 자체에는 접속 인자가 없다.
- **`unverified` 등급의 화면 노출 정책은 기획 결정 대기.** 47건 중 `average_tenure` 34건, `employee_count` 33건. **값이 틀렸다는 뜻이 아니라 대조할 두 번째 경로가 없다는 뜻이다.** 86은 수치와 사유를 내는 데까지만 했다.
- **동종업계 비교 응답의 98~99%가 값이 전부 null.** `company`는 3,930개사인데 지표 적재는 10개사(0.25%)라서다. 규격대로 동작하는 것이라 버그로 보지 않았지만, UX(빈 행 489개) · 성능 · 지표 대상 확대는 기획·백엔드 판단이 필요하다 (86에서 보고).

---

## 7. 반드시 지킬 원칙

과거 세션과 이번 작업에서 실제로 비싸게 배운 것들이다.

**① 검증 규칙이 파싱 규칙보다 먼저다.**
첫 R&D 시도에서 프로그램은 "성공 5/10"이라 보고했지만 실제로 맞은 건 1건이었다. SK하이닉스 R&D를 673만원으로 읽었다(실제 6.7조). **실패는 눈에 보이지만 틀린 성공은 안 보인다.**

**② 문서만 보고 필드명을 짐작하지 마라.**
평균근속 필드명을 `avrg_cnttk_sdytrn`으로 알고 있었으나 실제는 `avrg_cnwk_sdytrn`이었고 조용히 `None`이 나왔다. 새 API를 쓸 때는 `scripts/probe_api.py`로 **응답 원본을 먼저 찍어보라.**

**③ "회사마다 이름이 다르다"가 거의 모든 실패의 원인이다.**
이름으로 찾는 부분은 전부 `config/patterns.yaml`에 있다. **커버리지가 안 나오면 코드를 고치지 말고 이 목록을 늘려라.**

**④ 회사가 우리와 다르게 계산한 값은 버리지 말고 기록하라.**
한미반도체는 R&D 비율을 다른 분모로, LG전자는 근속을 다른 방식으로 계산했다. 차이를 `metric_evidence.gap_pct`에 남긴다.

**⑤ 근거 없는 숫자는 서비스에서 쓸 수 없다.**
모든 지표에 `verdict`·`source`·`rcept_no`·`evidence`(표 순번·행 라벨·원문 셀)를 남긴다.

**⑥ 수집과 정규화를 절대 합치지 마라.**
정규화는 `DartClient`가 아니라 읽기 전용 `RawStore`를 쓴다 — 네트워크로 나갈 수단 자체가 없어야 계층 분리가 코드로 강제된다. R&D 파서는 5번 고쳤다.

**⑦ 못 찾으면 추정하지 말고 명시적으로 실패시켜라.**
커버리지를 맞추려고 값을 채우면 안 된다. `not_found` / `rejected`로 남긴다. 단위를 모르면 자릿수가 통째로 틀린 값이 나온다 — 값이 있는 것보다 없는 게 낫다.

**⑧ 두 번 계산해서 같다고 검증된 게 아니다.**
`verify_db.py`의 검사 [2]는 정규화를 다시 돌려 비교하므로 **적재 단계만** 검증한다. 정규화 규칙이 틀렸다면 그냥 통과한다. 그래서 정규화를 쓰지 않는 독립 대조 [3]을 따로 뒀다.

---

## 8. 함정 모음 (실제로 걸린 것만)

### DART API

```
① zip 응답 판별      corpCode.xml · document.xml 은 zip. 실패 시엔 XML 에러 문서가 온다
                    → 매직바이트 'PK' 로 구분. 확장자·Content-Type 을 믿지 마라
② fs_div 처리        fnlttSinglAcnt    응답 행에 fs_div 있음 (연결·별도 혼재)
                    fnlttSinglAcntAll 응답 행에 fs_div 없음 (요청 파라미터일 뿐)
                    → 같은 함수로 처리하면 전체재무제표 행이 전부 필터링된다
③ status 013 은 정상  '조회된 데이터 없음'. 빈 결과로 처리해야 한다
                    → 오류로 처리하면 상장 이전 연도에서 파이프라인이 멈춘다
```

호출 간격 0.05초(초당 20회)로 3,930콜 연속 성공한 실측이 있다.

### 이번에 새로 걸린 것

```
④ DATABASE_URL 호스트   localhost 는 IPv6(::1) 먼저 → 무한 대기. 127.0.0.1 을 쓸 것
⑤ ksic_division.csv   BOM + 헤더·값 패딩 공백 + 쉼표 뒤 공백 때문에 따옴표 미인식
                      → utf-8-sig · strip · skipinitialspace 셋 다 필요.
                        안 하면 '전자 부품, 컴퓨터, ...' 가 4조각이 된다
⑥ db.upsert 의 시각 컬럼  테이블마다 다르다. company=updated_at, 착지=collected_at,
                      industry=둘 다 없음. 무조건 붙이면 적재가 통째로 실패
⑦ Docker Desktop 크래시  AppData\Local\Docker\run 의 stale 소켓(0바이트 reparse point)
                      때문에 기동 실패. 개별 삭제 불가 → 상위 폴더 이름을 바꿔라.
                      에러 창의 "Reset to factory defaults" 는 볼륨까지 날린다. 쓰지 마라
```

---

## 9. 막히면 볼 곳

| 궁금한 것 | 볼 곳 |
|---|---|
| 왜 이렇게 설계했나 (결정 10개 + 근거) | `DESIGN.md` 2장 |
| 계정명 후보·정규식·임계값 구체적인 값 | `DESIGN.md` 4장 + `config/patterns.yaml` |
| API별 응답 구조·필드 유무 | `DESIGN.md` 3장 + `API_NOTES.md` |
| 이번 티켓의 지시·확정 결정 | `docs/S15P21A504-84.md` |
| 검증 티켓(86)의 범위·완료 판정 | `docs/S15P21A504-86.md` |
| 확인을 마친 발견과 등록 기준 | `config/known_findings.yaml` |
| verdict 매핑표 (파서 12종 → 4종) | `V5__add_metric_evidence.sql` 하단 주석 |
| 백엔드 스키마 설계 근거 | `../docs/design/db-schema.md` |
| 브랜치·커밋·MR 규칙 | `../docs/conventions/git.md` |

---

## 10. 다음 사람이 먼저 할 일

1. **백엔드 답변 받기** — 6-1의 2번(기업개황 수집 범위). 이게 정해져야 `ceo`·`establishedDate`가 채워진다.
2. **스테이징 적재 후 재검증** — 접속 정보를 받아 아래 순서로 한 번 더 돌린다. 이번 검증은 로컬 백엔드 기준이다.

   ```bash
   # .env 의 DATABASE_URL 을 스테이징으로
   python scripts/probe_backend_api.py --base-url http://<스테이징>:8080   # 응답 원본 재수집
   python scripts/verify_all.py
   ```
3. **기획 결정 두 건 받기** — `unverified` 화면 노출 정책, 동종업계 비교의 값 없는 기업 처리 (6-5).
4. **정기 갱신을 자동화할 때 CI에 검증을 넣는다** — 86의 판단은 **지금은 넣지 않는다**였다. `Jenkinsfile`의 Verify 단계는 backend · frontend · infra가 병렬로 돌고 전부 DB 없이 검증하는데, 데이터 검증을 붙이면 PostgreSQL 컨테이너 · DART 인증키 · `.cache/` 305MB가 새로 필요해진다. 확정 데이터는 연 1회 갱신이라 매 커밋마다 검증할 이유가 약하다. **지금은 적재 후 사람이 `verify_all.py`를 돌리고**(3장 5단계), 정기 갱신 배치를 만들 때 그 마지막 단계로 넣어라.
5. **확장 여부 결정** — 타깃을 10개사에서 늘릴 계획이면 지금 정하는 게 좋다. 수집에 시간이 걸려 나중에 정하면 병목이 된다. 3,930개사 전부면 약 94,000콜(일 한도 20,000 → 5일), 사업보고서 원문만 약 18GB로 추정된다.
