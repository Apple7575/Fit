# 뉴스 PoC — 데이터 인계

**먼저 [93번 인계 안내](93-poc-decision.md)를 읽으면 된다.** 데이터 담당 범위는 수집·분석 결과와 재현 자료 전달까지다. 백엔드 API·DB·화면 구현은 포함하지 않는다.

## 문서

| 문서 | 용도 |
|---|---|
| [90 소스 조사](90-source-review.md) | 제공 정보·사용조건·미확정 사항 |
| [91 수집 결과](91-collection-result.md) | 최종 수집 품질·원문 확보 한계·수집 재실행 |
| [92 AI 검증](92-ai-evaluation.md) | 최종 모델·중요도 기준·하네스 결과·보존 근거 |
| [93 최종 판정·인계](93-poc-decision.md) | 전달 파일·필드·결측·실패·재실행 방법 |

## 실제 데이터

`data/news_poc/local_output/92-career-holdout/backend-handoff/`

- `candidates.json`: 새 검증 표본의 관련·형식 유효 후보 23건
- `excluded.json`: 무관·보류 7건
- `manifest.json`: 건수와 결측. 후보 전부 요약·직접 원문 URL·기업 코드 null

실험 데이터는 Git에서 제외된다. 공유할 때 파일을 따로 전달해야 한다. 기사 RSS 링크와 언론사 직접 원문 URL은 서로 다른 필드다. AI 점수는 취준생 유용성 0~10이며 카테고리는 없다.

## 코드

재사용 코드는 `pipeline/`, PoC 실행 도구는 `experiments/`, 단위 테스트는 `tests/`로 분리했다. 자세한 파일 역할과 실행은 [코드 안내](../../news_poc/README.md)를 따른다. 결과 폴더에는 Python 코드를 두지 않는다.

```powershell
python -m unittest discover -s data/news_poc/tests
```

폴더 정리 과정에서 임시 가상환경·다운로드 캐시·엑셀 및 이미지 미리보기·폐기된 기업 영향 실험·중복 초안을 제거했다. 현재 인계·검증·사람 검수 근거는 유지한다. `.env`는 공유하지 않는다.
