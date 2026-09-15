# Task 4 완료 보고 — 사업보고서 전용 재구축 모드

## 결과

`--business-report-only` 모드를 추가했다. 이 모드는 `--dart-archive` 없이는 DB 연결 전에 거부하고, `company` 마스터로 대상 기업만 검증한 뒤 정본 loader를 호출하지 않는다. DART 사업보고서 근거만 검증·upsert하며, 삭제 SQL도 `corp_code`와 `DART_BUSINESS_REPORT`로 제한한다.

## TDD RED 기록

각 테스트를 구현 전에 추가하고 다음 명령으로 실패를 확인했다.

| 계약 | RED 명령 | 확인한 실패 |
| --- | --- | --- |
| 전용 플래그 허용 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_parse_args_accepts_business_report_only_with_dart_archive -v` | `unrecognized arguments: --business-report-only` |
| archive 없는 조합 조기 거부 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_main_rejects_business_report_only_without_archive_before_database_connection -v` | `SystemExit not raised` |
| source type 거부 | `python -m unittest tests.rag_corpus.test_load.BuildCompanyRecordsTest.test_business_report_only_rejects_non_business_report_source_type -v` | `build_business_report_records` import 불가 |
| 기업 코드 불일치 거부 | `python -m unittest tests.rag_corpus.test_load.BuildCompanyRecordsTest.test_business_report_only_rejects_cross_company_record -v` | `ValueError not raised` |
| 빈 내용 거부 | `python -m unittest tests.rag_corpus.test_load.BuildCompanyRecordsTest.test_business_report_only_rejects_blank_content -v` | `ValueError not raised` |
| 동일 identity 축약 | `python -m unittest tests.rag_corpus.test_load.BuildCompanyRecordsTest.test_business_report_only_deduplicates_identical_source_identity -v` | 중복 record가 남음 |
| 정본 loader 미호출 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_business_report_only_uses_only_dart_records_without_loading_master_sources -v` | `run() got an unexpected keyword argument 'business_report_only'` |
| DART 전용 삭제 범위 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_business_report_only_actual_sync_scopes_delete_to_dart_source_type -v` | delete params에 `DART_BUSINESS_REPORT` 없음 |
| 문서 0건 보존 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_business_report_only_preserves_existing_records_when_no_source_documents_exist -v` | `write_status`가 `replaced` |
| CLI 플래그 전달 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_main_forwards_business_report_only_flag_to_run -v` | `business_report_only` kwargs 없음 |
| 일반 모드 유지 | `python -m unittest data.tests.rag_corpus.test_cli.BuildRagCorpusCliTest.test_default_mode_keeps_loading_master_sources_before_external_provider -v` | 처리 순서가 `provider`, `master` |

위 명령은 `C:\Users\SSAFY\Desktop\S15P21A504\.venv\Scripts\python.exe`로 실행했다.

## GREEN 및 회귀

다음 명령으로 전용 CLI·load 테스트 33개, RAG corpus 전체 관련 회귀 52개를 통과시켰다.

```powershell
& 'C:\Users\SSAFY\Desktop\S15P21A504\.venv\Scripts\python.exe' -m unittest discover -s tests/rag_corpus -v
```

결과: `Ran 52 tests ... OK`.

## 변경 파일

- `data/scripts/build_rag_corpus.py`: CLI 옵션, 전용 실행 경로, 실패 보류 처리
- `data/pipeline/rag_corpus/load.py`: 사업보고서 전용 입력 검증과 source type 한정 동기화 SQL
- `data/tests/rag_corpus/test_cli.py`: CLI/실행 경로/무쓰기/실패 보류 회귀 테스트
- `data/tests/rag_corpus/test_load.py`: 입력 검증·중복·삭제 범위 테스트

## 커밋

- 구현: `5be243b feat: add business report only corpus sync`

## 남은 위험

확실: 단위 테스트는 SQL의 삭제 범위와 파라미터를 검증했다.

추측/미검증: 실제 대표 5개사 PostgreSQL 전용 스키마에 연결하는 통합 실행은 이 작업 범위에서 수행하지 않았다. 실행 전 해당 DB에 `company`와 `rag_evidence` 테이블 및 `rag_evidence.source_type` 컬럼이 존재하는지 확인해야 한다.
