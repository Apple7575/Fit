# DATA — DART 수집·정규화 파이프라인

취준생용 기업분석 서비스의 데이터 파트. OpenDART에서 수집 → 정규화 → PostgreSQL 적재.

관련 Jira: **US-05 (S15P21A504-6)** DART 데이터 파이프라인 및 PostgreSQL 외

---

## 지금 상태

> 이 절과 아래의 13개사·10개사 수치는 초기 파이프라인 검증 시점의 기록이다. 최종 기업 시드는 상장사 2,662개사(`curated/seed/company.csv`)다.

**수집·정규화·로컬 DB 적재와 검증까지 완료했다.**

지표 4종을 13개사 × 5년 = 65건으로 검증했고 전부 교차검증을 통과했다.

| 지표 | 검증 결과 |
|---|---|
| 매출액 | 50/50 `verified` (3경로 교차검증, 불일치 0건) |
| 영업이익 | 50/50 (영업손실 4건 음수 정상 처리) |
| R&D / 매출 | 50/50 `high` (3경로 교차검증) |
| 직원수·1인평균급여·평균근속 | 50/50 (합계 행 대조 통과) |

문서는 `docs/`, 정식 구현은 `pipeline/`, 회귀 검증 기준선은 `tests/fixtures/normalize/`에 있다.

---

## 문서 (읽는 순서)

| 문서 | 내용 |
|---|---|
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | **여기부터.** 환경 세팅·재개 명령어 |
| [`docs/WORK_PLAN.md`](docs/WORK_PLAN.md) | 작업 계획. WP ↔ Jira 티켓 매핑, 일정 배치 |
| [`docs/BACKLOG_STATUS.md`](docs/BACKLOG_STATUS.md) | 백로그 13개 AC 단위 진행률 |
| [`docs/DESIGN.md`](docs/DESIGN.md) | 설계 결정 + 파싱 규칙(정규식·임계값) + 검증 수치 |
| [`docs/DATA_STORAGE_STANDARD.md`](docs/DATA_STORAGE_STANDARD.md) | **저장 기준의 정본.** raw/staged/curated 경계, 파일명·식별자 규칙, 시드 CSV 기준, Git 추적 범위 |
| [`docs/data_fields.csv`](docs/data_fields.csv) · [`docs/seed_csv_inventory.csv`](docs/seed_csv_inventory.csv) | 데이터 사전 / 테이블별 시드 CSV 보유 현황 |
| [`docs/news-poc/README.md`](docs/news-poc/README.md) | 뉴스 PoC 진행 현황·실행 방법·티켓별 조사 문서 |

---

## 실행

```bash
cd data
python -m pip install -r requirements.txt
cp .env.example .env      # DART_API_KEY 입력

python scripts/collect.py           # DART 원본 수집
python scripts/normalize.py         # 캐시 원본 정규화
python scripts/verify_normalize.py  # 기준선 150건 회귀 검증
```

### PostgreSQL RAG 코퍼스 구축

`DATABASE_URL`이 설정되어 있어야 한다. `--dry-run`은 정본을 읽고 변환·제외 건수만
집계하며 `rag_evidence`를 삭제하거나 삽입하지 않는다. 실제 구축은 기업 하나씩 독립
트랜잭션으로 동기화한다. 원본 파싱 실패 또는 다른 기업과 `evidence_id` 충돌한 기업은
종료 코드 `1`과 함께 기존 코퍼스를 보존한다. 같은 기업의 ID는 갱신하고, 이번 입력에 없는
같은 기업 근거만 삭제한다.

```bash
# 전체 기업을 정렬된 코드 순서로 검사만 한다
python scripts/build_rag_corpus.py --dry-run

# 한 기업만 재구축
python scripts/build_rag_corpus.py --corp-code 00126380

# 여러 기업만 재구축 (중복 코드는 한 번만 처리)
python scripts/build_rag_corpus.py --corp-code 00126380 --corp-code 00164779

# 전체 기업 코퍼스 재구축
python scripts/build_rag_corpus.py

# 로컬 사업보고서 ZIP만 포함해 DB를 바꾸지 않고 전수 계측한다
python scripts/build_rag_corpus.py --dry-run \
  --dart-archive C:/Users/SSAFY/Downloads/dart_local.zip \
  --embedding-dimension 1024

# 재현 가능한 순서로 지정 기업의 사업보고서 코퍼스만 구축한다
python scripts/build_rag_corpus.py \
  --corp-code 00126380 --corp-code 00164779 \
  --dart-archive C:/Users/SSAFY/Downloads/dart_local.zip
```

결과 JSON은 전체와 `companies[corp_code]`별 `company_count`, `record_count`, 정본
`input_counts`, `excluded_counts`, `elapsed_ms`를 반환한다. 기업별 `elapsed_ms`는 해당
기업의 DB context 시작부터 종료까지, 전체 `elapsed_ms`는 전수 구축 시작부터 JSON 생성까지
측정한다. 사업보고서 배치의
`documents`, `sections`, `paragraphs`, `tables`는 원본 입력 수이고,
`business_report_text_chunks`, `business_report_table_chunks`는 출력 청크 수다.
기업별 `external_input_counts`, `external_excluded_counts`는 사업보고서 소계다.
파싱 실패는 `failures`에 기업 코드·provider·원본 실패 계보를 남기며 해당 기업은
`write_status=skipped_due_to_source_failure`가 된다. `estimated_embedding_bytes`는
`record_count × embedding_dimension × 4`로 계산한 float32 벡터 본문 예상 바이트다.
차원은 양수만 허용하며 기본값은 `1024`; 테이블·인덱스·메타데이터 저장량은 포함하지 않는다.

### RAG 문서 임베딩 증분 구축

Flyway V26 적용과 `DATABASE_URL` 설정이 필요하다. 기본 모델은
`Qwen/Qwen3-Embedding-0.6B`이며 팀 GPU 서버의 vLLM pooling runner로 실행한다. 문서 입력은
`document_embedding_text` 계약으로 만들고, 질의에만 기업 공식 자료 검색 지시문을
붙인다. 기존 E5 기준선은 `requirements-embedding-cpu.txt` 또는
`requirements-embedding-gpu.txt`로 로컬 실행할 수 있다.

```bash
# 선택 건수만 조회한다. 모델 생성·다운로드·임베딩 저장은 하지 않는다.
python scripts/build_rag_embeddings.py --corp-code 00126380 --dry-run

# 기존 E5를 비교 기준선으로 로컬 실행한다.
python scripts/build_rag_embeddings.py \
  --model intfloat/multilingual-e5-large --device cuda --version document-v1
```

팀 GPU 서버에서는 기존 Qwen vLLM과 별도인 8001번 포트에 임베딩 API를 띄운다.
GPU는 팀에 배정된 1번만 사용하며 명시적 CUDA 실행이 실패하면 CPU로 우회하지 않고
서버 시작도 실패한다. Qwen 프로세스가 팀 할당 메모리를 사용 중이면 먼저 중지해야 한다.

```bash
# jupyter05의 vLLM 가상환경에서 실행한다.
# EMBEDDING_API_KEY는 저장소 밖의 보호된 환경 파일에서 주입한다.
bash scripts/run_rag_embedding_server.sh

# 개발 PC의 data/.env에 같은 EMBEDDING_API_KEY를 둔다.
# DB는 개발 PC가 읽고 GPU 서버에는 임베딩할 텍스트만 보낸다.
python scripts/build_rag_embeddings.py \
  --corp-code 00126380 \
  --corp-code 00164779 \
  --source-type DART_BUSINESS_REPORT \
  --batch-size 32 \
  --remote-url http://70.12.130.105:8001/v1
```

vLLM 원격 API 경로는 `POST /v1/embeddings`다. 응답 차원과 벡터 개수가 계약과 다르면 해당
배치를 저장하지 않는다. 이전 배치까지는 독립 커밋되므로 같은 명령으로 재실행하면
남은 근거만 처리한다. 이 경로는 기업 에이전트 공개 API가 아니라 GPU 추론 인프라의
내부 경로다.

기본 모델은 `Qwen/Qwen3-Embedding-0.6B`, 버전은 `document-v1`, 배치는 `32`다.
기업 코드 생략 시 전체 기업을 대상으로 하며, 알 수 없는 기업 코드는 모델 로드·저장 전에
거부한다. 정확히 같은 모델·버전에 벡터가 없거나 근거의 `content_hash`가 다른 행만
`corp_code, evidence_id` 순서로 선택한다. 조회 연결을 닫은 뒤 임베딩하며, 저장은 배치별
독립 트랜잭션이다. 실패한 배치는 롤백되고 이전 커밋은 남으므로 같은 명령으로 재실행한다.

성공·실패는 stdout 한 줄 JSON이며 실패 종료 코드는 `1`이다. `selected`는 시작 시점의
변경 대상 수, `unchanged`는 같은 모델·버전·해시로 이미 저장된 수, `embedded`는 이번 실행의
커밋된 수, `failed`는 실패 배치의 행 수다. 배치 처리 중 오류 JSON에도 이 집계가 포함된다.
오류 원문은 DB 인증정보 유출을 피하려고 출력하지 않는다. `dimension`은 실제 임베딩 차원이며,
dry-run에서는 기본 Qwen3 모델의 알려진 차원 `1024`를 쓰고 그 외 모델은 `null`로 표시한다.
dry-run의 `embedded`와 `failed`는 `0`이다. 동시 코퍼스 수정이 있으면 시작 집계와 처리량은
달라질 수 있으며, 이미 읽은 행의 수정은 다음 실행에서 해시 불일치로 다시 선택된다.

뉴스는 별도 흐름이다. 수집기는 `news_poc/pipeline/collect.py` 이고, 그 원본을 표준 구조로
정제·적재본으로 만드는 것은 아래 네 CLI 다. 네트워크를 호출하지 않는다.

```bash
python scripts/import_news_raw.py --from <수집기 --out 폴더>   # raw 로 복사 + 체크섬 대조 + manifest
python scripts/stage_news.py                                  # raw → staged
python scripts/build_news_seed.py                             # staged → curated/seed/news_article.csv
python scripts/verify_news.py                                 # 검증 14종
python -m unittest discover -s tests/news -t .                # 단위·통합 테스트
```

사업보고서 원문에서 뽑는 값은 또 다른 흐름이다 (S15P21A504-73). DART 정형 API 로는
못 얻는 부문별 매출·시설투자·기업 서술이고, 100개사 × 5년이 대상이다.

```bash
python scripts/select_business_report_universe.py   # 대상 100개사 → config/
python scripts/collect_business_reports.py          # 원문 XML 수집 (유일한 네트워크 단계)
python scripts/parse_business_reports.py            # 원문 → staged/business_report/
python scripts/extract_business_text_llm.py         # 의미 해석 항목 (팀 vLLM)
python scripts/build_curated_seed.py                # → curated/seed/ 7종
python scripts/verify_business_report.py --report   # 검증 8축 + 커버리지
```

LLM 단계는 `data/.env` 의 `LLM_KEY` 가 필요하다 (팀 vLLM 서버, `.env.example` 참고).
키가 없으면 그 단계만 건너뛰고 나머지는 그대로 돈다.

정규화는 `.cache/`의 API 응답 원본만 읽으며 네트워크를 호출하지 않는다. 캐시는 커밋하지 않으므로(330MB), 없으면 `scripts/collect.py`로 먼저 수집한다. 다른 위치의 캐시를 쓰려면 `DART_CACHE_DIR` 환경변수로 지정한다.

---

## 구조

```
data/
├── config/
│   ├── targets.csv             타깃 10개사 + KSIC 중분류 + 상장연도
│   ├── business_report_universe.csv  사업보고서 파싱 대상 100개사
│   ├── company_universe.csv    상장사 3,930건 + 업종 (F-04 적재 입력)
│   └── ksic_division.csv       KSIC 중분류 77개 코드→명칭
├── docs/                       설계·계획·진행상태 문서 + 데이터 사전
├── raw/                        원본 (출처별. gitignore)
├── staged/                     정제 결과 (재생성 가능. gitignore)
├── curated/seed/               DB 테이블별 적재본 CSV (7종)
├── manifests/                  수집·시드 계보 기록
├── pipeline/                   수집·정규화 정식 구현
│   ├── normalize/              매출·직원·R&D 지표별 정규화
│   ├── business_report/        사업보고서 원문 → 부문 매출·시설투자·기업 서술
│   └── news/                   뉴스 raw → staged → curated
├── scripts/                    수집·정규화·적재·검증 CLI
├── tests/fixtures/normalize/   정규화 회귀 검증 기준선
└── .cache/                     DART API 응답 원본 (gitignore)
```

세 단계(`raw`/`staged`/`curated`)의 경계와 Git 추적 범위는
[`docs/DATA_STORAGE_STANDARD.md`](docs/DATA_STORAGE_STANDARD.md) 에 있다. DART 원본은 아직
`.cache/` 에 평면 파일명으로 있고 이동은 별도 작업이다.

초기 프로토타입의 검증된 규칙은 `config/patterns.yaml`과 `pipeline/normalize/`로 이전했고, 기준 결과만 fixtures에 보존한다.

---

## 다음 작업

`docs/WORK_PLAN.md` 참고. 요약하면:

```
✔ WP-1   patterns.yaml               F-27 (-38) AC1
✔ WP-2   API 클라이언트                F-26 (-35) 완료, F-24 (-32) 완료
✔ WP-12  비교 대상 선정 규칙            F-19 (-29) 완료
✔ WP-3   DDL                         로컬 PostgreSQL 18 적용 완료
✔ WP-4   기업 마스터 적재               F-04 (-11) 완료 — 3,930행
✔ WP-5   수집 파이프라인                F-06 (-17) AC3, F-12 (-23) AC3
✔ WP-6   정규화 파이프라인              F-27 (-38), F-06, F-12 완료
✔ WP-7   Upsert 적재                  F-07 (-15), F-28 (-37) 완료
✔ WP-8   적재 검증                     F-13 (-21) 완료, F-30 (-39) 부분
  WP-9   실행 이력                     F-29 (-36)
  WP-10  미해결 파서 2건 / WP-11  다른 업종 확장 테스트
```

**티켓 11/13 완료.** 남은 것은 F-29(실행 이력)와 F-30의 API 노출값 대조(백엔드 필요).

로컬 검증 DB — 팀 `infra/`와 무관한 임시 컨테이너를 쓴다.

```bash
docker run -d --name dart-data-pg-local -p 127.0.0.1:55432:5432 \
  -e POSTGRES_DB=company_analysis -e POSTGRES_USER=ssafy -e POSTGRES_PASSWORD=... \
  -e "POSTGRES_INITDB_ARGS=--locale-provider=icu --icu-locale=ko-KR --encoding=UTF8" \
  -e TZ=Asia/Seoul postgres:18

# 스키마는 백엔드의 Flyway 마이그레이션을 쓴다 (S15P21A504-84 D-2).
# data/sql/ddl.sql 은 폐기했다.
cd ../backend/src/main/resources/db/migration
for f in $(ls V*.sql | sort -V); do
  docker exec -i dart-data-pg-local psql -U ssafy -d company_analysis -v ON_ERROR_STOP=1 -q < "$f"
done
cd -

python scripts/collect.py        # 원본 수집
python scripts/load_company.py   # industry 77 + 기업 마스터 3,930건 (FK 때문에 이게 먼저)
python scripts/load_raw.py       # DART 직원현황 착지 테이블
python scripts/load_metrics.py   # 지표 + 근거 적재
python scripts/verify_db.py --report   # 적재 검증 + 커버리지 리포트
```

> **현재 상태는 [`docs/HANDOFF.md`](docs/HANDOFF.md)를 보라.** 아래 WP 목록은 브랜치 38 시절 기록이다.

**남은 결정 2건**(`WORK_PLAN.md` 1장) — R&D 티켓 분리(D-2), `unverified` 노출 정책(D-3).
비교 대상 범위(D-1)는 **A: 타깃 10개사 내부**로 확정됐다.
