# 93 — 뉴스 PoC 최종 범위 판정

현재까지의 90~92번 결과를 종합한다. **Google RSS는 사용자 선택 PoC 소스로 유지한다. 제목 기반 후보 수집과 AI 분석 실행은 확인했으나, 운영 소스 확정·상장사 3,000개 확대는 아직 승인 가능한 상태로 검증하지 못했다.**

| 항목 | 판정 | 근거 |
|---|---|---|
| 회사명으로 기사 후보 수집 | Pass: 제한된 실험 범위 | [91번](91-collection-result.md): 삼성전자 및 일부 기업 실수집 |
| 전수 수집·완성 요약 제공 | 미확인 | RSS 상한, 설명이 제목 반복인 사례, 전체 기사 분모 없음 |
| 원문 URL 95% 확보 | Fail | 115건 중 확인 15건, 제한 응답 이후 95건 미실행 |
| 운영 저장·캐싱·AI 활용 조건 | 미확정 | [90번 조사 기록](90-source-review.md)의 미해결 조건. 이번에 법적 판단을 새로 내린 것은 아님 |
| 기존 관련성 모델 | 후보 유지, 잠정 기준 미달 | [92번](92-ai-evaluation.md): 독립 무작위 사람 검수 40건 Gemini 82.5%, 무관 오통과 19%, 보류 일치 0/2 |
| 사업·취준생 중요도 자동 실행 | 실행 검증 완료 | 새 30건, 반복 포함 70개 응답 정규화 후 유효 64개 |
| 사업·중요도 반복 안정성 | 개선 필요 | 사업 14/20 일치, 비교 가능한 점수 19건 중 5건이 2점 초과 변동 |
| 실제 취준생 유용성 정확도 | 미측정 | 기존 30건 AI 초안에 사용자 동의. 새 표본은 사용자 요청으로 자동 하네스만 실행 |

## 데이터 담당 인계 범위

데이터 담당 산출물은 **수집·분석 데이터, 필드 설명, 결측·실패 기준, 검증 결과와 재실행 방법**이다. DB 설계·적재 API·화면 구현은 인계받는 담당자의 영역이며 이번 작업에 포함하지 않는다. 현재 데이터로 어떤 서비스를 제공할지는 팀에서 결정한다.

## 먼저 전달할 파일

저장소 루트 기준 `data/news_poc/local_output/92-career-holdout/` 아래에 있다. 아래 23건은 **새 30건 검증 표본에서 추린 인계 후보**이며, 전체 수집량이나 사람이 정답으로 확정한 기사 23건이라는 뜻이 아니다.

| 파일 | 내용 |
|---|---|
| `backend-handoff/candidates.json` | AI가 관련으로 판정했고 형식 검사를 통과한 삼성전자 기사 23건. 인계의 기본 데이터 |
| `backend-handoff/excluded.json` | 무관·보류 7건의 ID·판정·형식 상태. 제목과 원자료는 dataset에서 ID로 조회 |
| `backend-handoff/manifest.json` | 인계·제외 건수, 결측 건수, 미적재 상태 |
| `dataset.json` | 검증에 사용한 원래 30건의 제목·날짜·RSS 링크·출처. 사람 정답은 비어 있음 |
| `analysis/input.json` | 사업·중요도 분석에 실제 사용한 30건 입력. 관련성은 기존 모델 판정 |
| `analysis/predictions-1.json` | 첫 실행 전체 결과. 이후 2·3번 파일은 반복 검증 결과 |
| `analysis/business_catalog.json`, `analysis/prompt.txt` | 사용한 삼성전자 사업 목록과 중요도 판단 지침 |
| `harness-result.md`, `harness-result.json` | 자동 검증 결과와 비용·반복 안정성 |
| `analysis/run-*-batch-*.json` | 원시 응답·정규화 결과·사용량. 문제 추적에 필요한 실행 증거 |

폴더 이름 `backend-handoff`는 이전 작업에서 붙인 이름이며 API 구현을 의미하지 않는다. 데이터 인계 폴더로 그대로 사용해 불필요한 복사본을 만들지 않는다.

**공유 주의:** `local_output/`은 Git에서 제외되어 있으므로 코드 커밋만으로 위 파일이 전달되지 않는다. 기본 전달물은 candidates·excluded·manifest와 이 문서이며, 재현까지 필요한 경우 해당 실행 폴더와 입력 출처 파일도 함께 전달한다. `.env`와 API 키는 포함하지 않는다.

## 필드 설명

JSON이 기준 형식이다. 문자열 `"null"`이나 빈 문자열로 바꾸지 않고 JSON null을 유지한다.

| 필드 | 의미·형식 | 현재 23건 |
|---|---|---|
| `sample_id` | 이번 평가 안의 ID. 영구 기사 ID가 아님 | 있음 |
| `company_name` | 분석 대상 기업명 | 삼성전자 |
| `corp_code` | 기업 마스터와 연결할 DART 고유번호 | 모두 null. 매핑 미완료 |
| `article_key` | 수집 코드가 만든 기사 식별 키 | 있음 |
| `title` | 수집한 기사 제목 | 있음 |
| `description` | 실제 확보한 설명·요약 입력 | 모두 null |
| `published_at` | 시간대가 포함된 ISO 8601 기사 시각 | 있음. UTC 보존, 날짜 구분은 KST |
| `original_url` | 확인된 언론사 직접 원문 URL | 모두 null |
| `rss_link` | Google 뉴스가 제공한 개별 기사 링크 | 있음. RSS 피드 전체 주소가 아님 |
| `business_status` | 특정 사업·회사 전체·여러 사업·정보 부족 구분 | AI 판단 |
| `related_business` | 특정 사업으로 판단했을 때 사업명 | 나머지 상태는 null |
| `importance_score` | 일반 취준생의 지원 준비 유용성, 정수 0~10 | AI 점수. 정확도 아님 |
| `analysis_metadata` | 점수 축·사업 및 점수 근거·보류 사유 | AI가 작성한 근거 |
| `model`, `rubric` | 모델과 점수 기준 식별값 | gemini-2.5-flash-lite / career-v1 |
| `relevance` | 회사 관련 여부 | 인계 후보는 related만 포함 |
| `schema_valid` | 허용된 형식·값 검사 통과 여부 | true. 의미가 정확하다는 뜻은 아님 |

카테고리는 분류하지 않으며 인계 필드에도 없다. 기사 원문 본문을 제공하거나 AI 학습용으로 사용 가능하다고 확정한 데이터가 아니다.

### 사업과 중요도 해석

- `specific`: 특정 사업 하나. `related_business`에 제공 목록의 사업명을 넣는다.
- `company_wide`: 특정 사업에 한정되지 않는 회사 전체 이슈. 사업명은 null.
- `multiple`: 대상 회사의 여러 사업을 함께 다룸. 사업명은 null. 여러 기업이 등장한다는 뜻이 아님.
- `insufficient`: 제목·설명만으로 사업을 특정할 수 없음. 사업명은 null.
- `not_applicable`: 관련성 판정이 무관·보류여서 후속 분석 대상 아님. 인계 후보에서 제외.

중요도는 `company_understanding`(기업 이해 0~4) + `job_connection`(직무 연결 0~3) + `application_use`(지원동기·면접 활용 0~3) 합계다. 회사에 미치는 경제적 영향이나 주가 중요도 점수가 아니다. 특정 지원 직무를 개인화한 점수도 아니다.

## 결측·실패 처리 기준

1. 요약이 없으면 null이다. 제목을 복사해서 요약을 만든 것처럼 전달하지 않는다.
2. 직접 원문 URL이 없으면 null이다. RSS 링크를 original_url에 넣어 원문 확보로 계산하지 않는다.
3. 사업명이 null이어도 실패는 아닐 수 있다. business_status로 전사·복수·정보 부족을 구분한다. 사업 정보 부족과 중요도 판단 가능 여부도 별개다.
4. 점수 0은 판단 결과 유용성이 없다는 뜻이다. 정보가 부족해 점수 축을 판단할 수 없으면 그 축과 합계는 null이다.
5. 관련성이 무관·보류이면 인계 후보에서 제외한다. 모델 판정 자체의 오판 가능성은 남아 있다.
6. 필수 근거 누락·허용되지 않은 사업명·점수 오류 등 형식 실패도 제외한다. 원시 응답은 남겨 재검토할 수 있게 한다.
7. 기존 근거 재사용·단일 사업 필드 비우기·합계 계산 같은 정규화는 원시 응답과 구분한다. 사업 상태나 점수 축을 임의로 바꾸지 않는다.
8. 기사 키 중복과 같은 사건의 다른 기사는 다르다. 다른 기업 분석까지 묶어 삭제하지 않는다. 사건 그룹은 중복 탐색 보조값이며 의미적 동일 사건을 완전히 검증한 결과가 아니다.

이번 첫 30건은 관련 23·무관 6·보류 1건이며, 형식 실패 4건이 무관·보류 7건 안에 포함된다. **제외 건수를 7+4=11건으로 합산하지 않는다.** 반복 포함 70개 응답의 실패 6개는 별도 검증 통계다.

## 검증 결과와 전달할 한계

- 수집: 회사명 검색으로 후보 수집 가능. Google RSS 결과 상한 때문에 전수 수집 보장 불가.
- 관련성: 별도 무작위 사람 검수 40건에서 33건 일치(82.5%). 작은 표본이며 잠정 통과 기준은 미달.
- 새 사업·중요도: 첫 실행 형식 유효 26/30, 관련 기사 점수 출력 23/23. 반복 포함 원시 형식 유효 41/70, 정규화 후 64/70.
- 반복성: 사업 상태·값 14/20 일치. 세 번 유효 점수가 있는 19건 중 5건은 2점 넘게 변동.
- 비용: 새 30건의 관련성+사업·중요도 한 번 실행 추정 50.186 GMS Credit. 반복 포함 실험 전체 111.144 Credit. 대량 실행 비용 보장은 아님.
- 실제 취준생 유용성 정확도는 미측정. 기존 30건 AI 초안에 사용자 동의가 있고, 새 표본은 사용자 요청에 따라 자동 하네스만 수행.

요약·직접 원문 URL 결측과 사용조건 미확정은 팀에 전달할 제약이다. 데이터 담당에게 API 구현이나 화면 구성 결정을 요구하는 항목이 아니다.

## 재실행 방법

아래 명령은 **저장소 루트**에서 Python으로 실행한다. 로컬 산출물 경로는 이 문서의 표와 같다.

### 기존 결과 확인·인계 파일 재생성 — 추가 API 호출 없음

```powershell
python -X utf8 -m data.news_poc.experiments.audit_career
python -X utf8 -m data.news_poc.experiments.export_handoff
python -m unittest discover -s data/news_poc/tests
```

`experiments/audit_career.py`는 저장된 3회 예측·배치·관련성 실행 기록을 읽는다. `experiments/export_handoff.py`는 dataset·첫 예측과 각 행의 source_file을 읽는다. 따라서 실행 폴더 외에도 `collected/results/collection_metadata.json`과 `today-collected/results/collection_metadata.json`을 보존해야 한다. 두 명령은 해당 집계·인계 파일을 다시 쓰므로 수동 수정본이 있으면 별도 보존한다.

### 같은 표본의 모델 실행 재개 — 캐시가 없으면 비용 발생

```powershell
python -X utf8 -m data.news_poc.experiments.gms_compare --input data/news_poc/local_output/92-career-holdout/dataset.json --out data/news_poc/local_output/92-career-holdout/relevance --model gemini-2.5-flash-lite --predict-only
python -X utf8 -m data.news_poc.experiments.business_evaluation --out data/news_poc/local_output/92-career-holdout/analysis --rubric career --repair-contract
```

키는 실행자의 `data/.env`에 GMS_KEY로 준비한다. 원본 배치가 온전히 있으면 재사용하며, 없는 배치는 호출한다. 입력·프롬프트 해시가 다르거나 실패한 배치가 있으면 무작정 덮어쓰지 말고 원인을 확인한다. 관련성 결과를 새로 바꾸면 `analysis/input.json`의 relevance도 ID 기준으로 다시 연결해야 하므로 위 두 명령만으로 임의 새 표본을 처리했다고 간주하지 않는다.

현재 사업 평가 스크립트는 **삼성전자 30건, 관련 최대 20건 추가 2회**의 PoC 전용이다. 새 기업·대량 실행은 사업 목록, 입력 생성과 실행 계획을 별도로 준비해야 한다. 일반 운영 배치가 완성된 상태가 아니다.

## 데이터 담당 완료 사항과 후속 범위

현재 인계 데이터·필드 설명·결측/실패 기준·검증 결과·재실행 안내를 준비했다. 회사 코드 매핑은 미완료 상태로 명시했다. 커밋·외부 전달은 아직 하지 않았다.

추가로 데이터 담당에게 요청할 수 있는 일은 기업 마스터를 이용한 코드 매핑, 대상 기업 확대, 요약·원문 확보 실험, 분석 안정성 개선이다. 어느 것도 이번 인계 자료 준비에 자동으로 포함하지 않는다. DB·API·화면 구현과 서비스 운영 범위 결정은 해당 담당자와 팀에 인계한다.
