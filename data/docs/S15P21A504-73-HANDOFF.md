# S15P21A504-73 이어서 하기

사업보고서 데이터 작업. **네 표 모두 100개사 × 5개년으로 채웠다. 이 티켓 범위는 끝났다.**

- 브랜치 `feature/S15P21A504-73-business-report-data` (develop 에서 분기, 미푸시)
- 마지막 갱신 2026-09-09

---

## 1. 끝난 것

| 시드 | 넣은 값 | 커버리지 | 커밋 |
|---|---|---|---|
| `company_metric.csv` | `rd_expense` | 319 기업-연도 · 70개사 | `9db4996` |
| `segment_metric.csv` | `segment_revenue` 1,139행 | 298 기업-연도 · 68개사 | `9db4996` |
| `company_activity.csv` | `facility` 1,419행 | 286 기업-연도 · 61개사 | `9db4996` |
| `company_text.csv` | 6종 11,203행 | 100개사 | `49e777e`·`?` |

`scripts/verify_business_report.py` 7축 전부 통과 상태다.

원문 487건(100개사 × 5년)은 `.cache/document_*.xml` 에 있다. 파싱 결과는
`staged/business_report/` 에 있고 **둘 다 Git 에 없다** — 지우면 다시 받아야 한다
(수집 약 3분, 파싱 약 35분).

---

## 2. company_text 의 LLM 항목 5종 — 다시 돌릴 때

`main_business` · `business_keyword` · `new_business` · `strategy_change` · `rd_field`

### 지금 상태

100개사 × 5개년 = 487문서를 전부 처리했다 (`staged/business_report/text_llm.csv`).

    main_product      4,052행   100개사   표 파싱 (generated_at 비어 있음)
    business_keyword  3,607행   100개사   LLM
    rd_field          2,569행   100개사   LLM
    main_business       487행   100개사   LLM  (문서마다 1행)
    new_business        359행   100개사   LLM  (문서의 74%)
    strategy_change     129행   100개사   LLM  (문서의 26%)

new_business·strategy_change 가 희소한 것은 결측이 아니다. 신규 사업과 전략 변화를
그 해에 밝히지 않은 것이고, 근거가 없으면 행을 만들지 않는다(팀장 기준 4항).

`data/.env` 의 `LLM_KEY` 가 필요하다. 서버가 죽어 있으면
`bash vllm-setup.sh start` (jupyter05).

### 처리 속도 — 앞선 추정이 틀렸다

**실측 6.1건/분이다.** 어제 1.1건/분으로 적었던 것은 8MB XML 487건을 파싱하는
작업이 같은 PC 에서 동시에 돌고 있을 때 잰 값이라 클라이언트 쪽이 밀린 것이었다.
파싱이 끝난 뒤 단독으로 돌리니 200건이 33분에 끝났다.

그래서 시간 때문에 범위를 줄일 이유는 사실상 없다.

    50개사   241문서   33분   (6.1건/분)
    100개사  487문서   +37분  (6.7건/분) — 실행 완료

프롬프트를 고쳐 다시 만들려면 아래로. `--redo` 는 전부 다시 만든다.

```bash
python scripts/extract_business_text_llm.py --companies 100 --redo
python scripts/build_curated_seed.py --only company_text
python scripts/verify_business_report.py --report
```

---

## 3. 이 작업에서 실측으로 잡은 함정

되짚을 일이 있을 때를 위해 남긴다. 근거는 각 커밋 메시지와 코드 주석에 있다.

| 무엇 | 증상 | 자리 |
|---|---|---|
| 단위 목록에 십억원·조원이 없었다 | SK하이닉스 시설투자 17.96조를 1.8조로 | `patterns.yaml` `rnd.units` |
| 단위를 문자열 전체에서 찾았다 | 삼성전자 캡션의 "53.6조원" 서술이 걸려 1만 배 | `doc.unit_from_blob` |
| 금액 열 첫 일치 채택 | LS 가 **향후**투자액을 읽어 353억 → 61백만원 | `facility._header_row` |
| 달러 금액 | 효성티앤씨 `$15백만` → 15원 | `facility.extract` |
| 목적 자리에 투자기간 | 한국전력공사, 열이 밀려 금액도 틀림 | `period_in_purpose` |
| 부문표 대신 매출유형표 | 삼성전자 '제ㆍ상품/용역' 도 합계가 맞아 통과 | `segment.exclude_cell` |
| 소계 행을 부문으로 셈 | 삼성전자 2021 '부문 계' 로 DS부문 이중 계상 | `segment.exclude_row` |
| LLM 이 프롬프트 예시를 베낌 | 삼성전자 답에 '이차전지 양극재'(안 하는 연구) | `llm._clean_list` 원문 대조 |

마지막 것이 가장 위험했다. 문구로는 못 막아서 **목록형 항목은 값이 원문에 문자열로
있는지 대조하고 없으면 버린다.** 요약인 `main_business`·`strategy_change` 는 대조를
걸 수 없으므로 그 두 항목은 여전히 사람이 표본 확인을 해야 한다.

---

## 4. 아직 남은 의존·한계

- **V17(MR !82) 미머지.** `rd_expense` 가 `metric` 카탈로그에 없어 로컬 DB 적재는
  FK 위반으로 실패한다. 시드 CSV 자체는 완성돼 있다.
- **뉴스 적재는 별개로 깨져 있다.** `pipeline/news/schema.py` 가 V13 이전을 본다
  (`company_news`/`category`). 이 티켓 범위가 아니라 손대지 않았다 — 백엔드가
  S15P21A504-121 코멘트에 적어 둔 건이다.
- **시설투자에서 셀이 밀린 행**은 인접 기간 열을 읽는다. 자릿수는 맞고 기간 구분만
  어긋난다. 근거는 `facility.py` 머리주석.
- **LLM API 키가 대화에 노출됐다.** 팀 안내 6절의 교체 대상이다. 교체하면
  `data/.env` 의 `LLM_KEY` 한 줄만 바꾸면 된다.
