# DATA — DART 수집·정규화 파이프라인

취준생용 기업분석 서비스의 데이터 파트. OpenDART에서 수집 → 정규화 → PostgreSQL 적재.

관련 Jira: **US-05 (S15P21A504-6)** DART 데이터 파이프라인 및 PostgreSQL 외

---

## 지금 상태

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

정규화는 `.cache/`의 API 응답 원본만 읽으며 네트워크를 호출하지 않는다. 캐시는 커밋하지 않으므로(330MB), 없으면 `scripts/collect.py`로 먼저 수집한다. 다른 위치의 캐시를 쓰려면 `DART_CACHE_DIR` 환경변수로 지정한다.

---

## 구조

```
data/
├── config/
│   ├── targets.csv             타깃 10개사 + KSIC 중분류 + 상장연도
│   ├── company_universe.csv    상장사 3,930건 + 업종 (F-04 적재 입력)
│   └── ksic_division.csv       KSIC 중분류 77개 코드→명칭
├── docs/                       설계·계획·진행상태 문서
├── pipeline/                   수집·정규화 정식 구현
│   └── normalize/              매출·직원·R&D 지표별 정규화
├── scripts/                    수집·정규화·적재·검증 CLI
├── tests/fixtures/normalize/   정규화 회귀 검증 기준선
└── .cache/                     API 응답 원본 (gitignore)
```

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
python scripts/load_raw.py       # DART 원본 착지 테이블
python scripts/load_metrics.py   # 지표 + 근거 적재
python scripts/verify_db.py --report   # 적재 검증 + 커버리지 리포트
```

> **현재 상태는 [`docs/HANDOFF.md`](docs/HANDOFF.md)를 보라.** 아래 WP 목록은 브랜치 38 시절 기록이다.

**남은 결정 2건**(`WORK_PLAN.md` 1장) — R&D 티켓 분리(D-2), `unverified` 노출 정책(D-3).
비교 대상 범위(D-1)는 **A: 타깃 10개사 내부**로 확정됐다.
