# 다기업 JD 연결 초안 라벨 검토

## 검토 기준

JD 요구사항을 필요한 근거로 나눈 뒤 사용자 원문에 각 근거가 명시됐는지 확인한다. 단어가 비슷하다는 이유로 근거를 인정하지 않고, 인용문이 사용자 원문에 실제로 존재해야 한다. 모든 필수 근거가 있으면 `SUPPORTED`, 일부만 있으면 `PARTIALLY_SUPPORTED`, 하나도 없으면 `NOT_SUPPORTED`로 판정한다.

## 토스뱅크 ML Backend Engineer

| 요구사항 | 초안 라벨 | 검토 결과 | 판단 근거 |
|---|---|---|---|
| 서버 개발 및 운영 | `SUPPORTED` | 유지 | Kotlin, 주문 API 개발, 운영 행동이 모두 명시돼 있다. |
| 서비스 아키텍처 및 코드 구조 | `NOT_SUPPORTED` | 유지 | Spring Boot API 구현은 있으나 아키텍처 설계 판단과 안정적인 코드 구조는 없다. |
| Kubernetes 배포 및 모니터링 | `SUPPORTED` | 유지 | Kubernetes 배포와 Prometheus 기반 오류율·응답시간 모니터링이 명시돼 있다. |
| 대규모 트래픽 또는 높은 SLA | `NOT_SUPPORTED` | 유지 | 트래픽 규모, SLA와 해당 조건에서의 프로덕션 운영은 없다. |

`Kubernetes 배포 및 모니터링`은 운영 안정성을 직접 단정하는 표현은 없지만 오류율과 응답시간을 모니터링한 행동이 있다. 현재 필요 근거 계약인 환경·배포·모니터링 세 항목은 모두 충족하므로 `SUPPORTED`를 유지한다. 이후 JD 분해 정책에서 `안정적으로 운영`을 별도 필수 근거로 둘 경우 다시 검토해야 한다.

## 카카오모빌리티 자율주행 개발품질 평가 엔지니어

| 요구사항 | 초안 라벨 | 검토 결과 | 판단 근거 |
|---|---|---|---|
| 성능 목표와 평가 방법론 | `PARTIALLY_SUPPORTED` | 유지 | 재현 시나리오와 정밀도 지표는 있으나 목표 성능을 설정한 내용은 없다. |
| 자율주행 기능 및 성능 검증 | `NOT_SUPPORTED` | 유지 | 폐쇄장·실도로 환경과 자율주행 시스템 테스트 수행은 명시되지 않는다. |
| 주행 데이터 분석 및 트러블슈팅 | `SUPPORTED` | 유지 | 주행 로그 분석, 오류 조건 파악, 제어 로직 수정안이 모두 있다. |
| 프로그래밍 언어 기반 데이터 분석 | `SUPPORTED` | 유지 | Python을 사용해 LiDAR 주행 로그를 분석했다. |
| 차량 네트워크 통신 이해 | `NOT_SUPPORTED` | 유지 | ROS2 프로젝트만으로 차량 네트워크 통신 지식이나 활용을 인정할 수 없다. |

## 결론

오프라인 근거 검토에서는 초안 9건을 모두 유지하는 것이 타당하다. 2026-09-13 사용자가 9개 라벨을 그대로 승인해 `label_status=HUMAN_APPROVED`, `evaluation_context=CROSS_COMPANY_HOLDOUT`으로 확정했다.

Qwen 교차검증 실행 명령은 다음과 같다.

```powershell
python -m ai.scripts.run_jd_pairwise_evidence_judge `
  --case ai/evals/jd_coaching/cases/tossbank-ml-backend-holdout-001.json `
  --document ai/evals/jd_coaching/sources/tossbank-ml-backend-2026.json `
  --env-file ai/.env `
  --reference-label ALL `
  --document-scope relevant-sections `
  --output outputs/jd-coaching/tossbank-draft-label-review.json
```

카카오모빌리티도 대응하는 case와 source 경로로 동일하게 실행한다. 확정 전 `DRAFT` 결과에는 `official_metric_eligible=false`가 기록되고, 확정된 두 사례는 공식 다기업 평가에 포함한다.

## 확정 후 기준선 결과

2026-09-13 확정 라벨을 기준으로 Qwen에 JD 관련 섹션과 연결 조합을 한 건씩 전달했다. 두 실행 결과는 `aggregate_jd_pairwise_runs.py`로 합산했다.

| 지표 | 결과 |
|---|---:|
| 연결 수 | 9 |
| 라벨 Accuracy | 0.7778 |
| 라벨 Macro F1 | 0.7222 |
| 필요 근거 Precision | 0.8667 |
| 필요 근거 Recall | 1.0000 |
| 존재하지 않는 인용문 비율 | 0.0000 |
| 총 토큰 | 10,780 |
| 연결당 평균 토큰 | 1,197.78 |

오답은 두 건이다.

1. 토스뱅크 `대규모 트래픽 또는 높은 SLA`: 규모나 SLA가 없는데 일반적인 운영 경험을 조건부 프로덕션 운영 근거로 인정해 `PARTIALLY_SUPPORTED`로 과대 판정했다.
2. 카카오모빌리티 `자율주행 기능 및 성능 검증`: 주행 로그 분석과 시나리오 작성을 실제 시스템 테스트 수행으로 확대 해석해 `PARTIALLY_SUPPORTED`로 과대 판정했다.

두 사례 모두 인용문은 실제 원문에 있었지만 JD가 요구한 조건을 충족하는 인용은 아니었다. 현재 방식은 인용문 존재 검증에는 강하지만 조건부 의미와 명시적 수행 행동을 엄격하게 제한하는 데 부족하다. 이 9건은 결과를 확인했으므로 이후 개선 방식의 최종 일반화 성능을 재는 홀드아웃으로 재사용하지 않는다.
