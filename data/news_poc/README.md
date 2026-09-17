# 뉴스 데이터 코드

## 남긴 구조

```text
pipeline/                 재사용할 수집·분석 규칙
  collect.py              회사명·기간 RSS 수집
  normalize.py            파싱·중복·CSV 처리
  gms_client.py           GMS 호출·응답 검사
  business_analysis.py    사업·취준생 중요도 규칙
  metrics.py              관련성 평가 계산
experiments/              현재 PoC 재실행 도구 4개
  gms_compare.py          관련성 모델 실행
  business_evaluation.py  삼성전자 30건 사업·중요도 반복 분석
  audit_career.py         저장 결과의 하네스 집계
  export_handoff.py       인계 데이터 생성
tests/                    핵심 단위 테스트 5개
local_raw/                원본 데이터
local_output/             분석·검수·인계 결과
```

`experiments`는 실제 표본을 처리하는 도구이며 모델 실행 시 비용이 발생할 수 있다. `tests`는 고정 입력과 가짜 API 응답으로 코드 오류를 검사하며 실제 GMS를 호출하지 않는다.

단위 테스트는 수집, 파싱·출력, GMS 응답·정답 미전송·캐시 확인, 사업·점수 검사, 평가 계산에 한정한다. 과거 통계 모델·혼합 방식·원문 접근·표본 선정 실행기와 전용 테스트는 제거했다. 과거 결과와 사람 검수 기록은 데이터로 보존하지만, 삭제한 실험 전체를 재실행할 수 있다고 보장하지 않는다.

## 실행

저장소 루트에서 실행한다.

```powershell
python -X utf8 -m data.news_poc.pipeline.collect --help
python -X utf8 -m data.news_poc.experiments.gms_compare --help
python -X utf8 -m data.news_poc.experiments.business_evaluation --help
python -X utf8 -m data.news_poc.experiments.audit_career
python -X utf8 -m data.news_poc.experiments.export_handoff
python -m unittest discover -s data/news_poc/tests
```

집계·인계 도구는 현재 고정된 로컬 표본을 읽어 파일을 재생성한다. 30건 평가 실행기는 운영용 대량 배치가 아니다. 데이터 설명·결측·한계는 [인계 문서](../docs/news-poc/93-poc-decision.md)를 따른다.
