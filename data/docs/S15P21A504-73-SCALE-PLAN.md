# 사업보고서 파이프라인 — 전 상장사 확대 설계

100개사로 검증한 파이프라인을 남은 2,499개사로 넓힌다. **하드웨어가 확정돼서
구상이 아니라 설계다.**

- 작성: 데이터 담당 (tpdms3048)
- 날짜: 2026-09-09
- 관련: S15P21A504-73 (MR !85), 팀장 하드웨어 회신
- 인프라 담당과 볼 문서는 [INFRA-DESIGN](S15P21A504-73-INFRA-DESIGN.md) 으로 나눴다
- 시간·용량은 전부 **100개사 실행에서 잰 값**의 외삽이다. 어디서 쟀는지 함께 적는다

---

## 0. 확정된 자원

| | 사양 | 역할 |
|---|---|---|
| **EC2 A** | 4 vCPU(물리 2코어) · 15GiB · 307GB 여유 | NameNode · ResourceManager · DataNode · NodeManager · Kafka |
| **EC2 B** | 동일 | DataNode · NodeManager |
| **jupyter05** | L40S 48GB 중 **약 23GB 할당** (GPU 1의 절반) | vLLM 추론 전용. 클러스터에 넣지 않는다 |
| 팀 개발 PC | — | 수집·오케스트레이션·(잠정) LLM 컨슈머 |

- 모델은 **Qwen3-32B-AWQ 그대로.** 가중치 18.2GB + KV 1.9GB = 22.7GB 로 할당 안에
  들어간다. 모델을 낮출 이유가 없고, 따라서 **프롬프트 재검증도 없다**
- GPU 1의 나머지와 GPU 0·2·3 은 다른 팀 것이다. **동시 요청은 4로 고정한다**
- HDFS replication = 2 (DataNode 2개)

---

## 1. 남은 규모

| | 처리함 | 남음 |
|---|---|---|
| 기업 | 100 | 2,499 |
| 원문(기업 × 연도) | 487 | 11,395 |
| 원문 용량 | 2.95GB | 약 69GB |

접수번호는 이미 다 갖고 있다 — `staged/opendart/financials.csv` 에 11,882건.
목록 조회 API 를 다시 돌리지 않는다.

**용량은 충분하다.** 69GB × replication 2 = 138GB. 물리 여유 614GB, OS·로그를 뺀
실사용 목표 250GB 안에 들어간다.

---

## 2. 병목과 예상 시간

### 실측값

| 단계 | 실측 | 근거 |
|---|---|---|
| 수집 | 340건/분 | 425건 받는 데 걸린 시간 |
| 파싱 | 4.25초/건, 프로세스당 약 450MB | 487건 2,072초 |
| LLM | 9.0초/건 (문서당 2회 호출) | 246건 2,220초 |

### LLM 동시 요청 — 실측

| 동시 | 9/9 (한산) | 9/10 (경합) |
|---|---|---|
| 순차 | 8.6건/분 | 10.3건/분 |
| 2 | 17.5 (2.0배) | 14.7 (1.4배) |
| **4** | **33.6 (3.9배)** | **25.5 (2.5배)** |
| 5 | — | 26.3 (2.6배) |
| 6 | — | 26.2 (2.5배) |
| 8 | 29.1 (3.4배) | 23.5 (2.3배) — 4보다 느리다 |

**가속이 날마다 다르다. GPU 1의 나머지 절반을 다른 팀이 쓰기 때문이다.**

    9/9  가속 3.9배 → 11,395건에 7.3시간
    9/10 가속 2.5배 → 11,395건에 11.4시간

**원인은 메모리가 아니라 연산 경합이다** (팀장 회신). 메모리는 절반씩 나뉘어 있지만
연산 코어는 같은 카드를 두 팀이 나눠 쓴다. 시간대를 골라도 통제할 수 없다.
그래서 **11~12시간**으로 잡는다 — 앞 판의 7.3시간은 한산할 때 잰 값 하나였다.

동시성을 올려도 이득이 없다는 것을 3회 반복 측정으로 확인했다(동시 4·6·8·10 중앙값
28·22.7·22·23.9). 같은 설정 안의 편차가 설정 간 차이보다 크다. 자세한 것과 vLLM
설정값은 [INFRA-DESIGN](S15P21A504-73-INFRA-DESIGN.md) 6장에 있다.

동시 4·5·6이 26건/분 근처로 평평하고 8에서 꺾인다. **동시 수를 올려도 이 벽은 안
넘는다** — 처리량 한계는 우리가 받은 할당(약 23GB · KV 캐시 1.9GB)이 정한다.
그래서 파티션은 4로 둔다(5·6은 처리량이 같은데 지연만 는다).

### 파싱 — EC2 2노드 기준

전체 8 vCPU 지만 **물리 코어는 4개**다 (노드당 2코어 × 2 스레드). lxml 파싱은
CPU 바운드라 하이퍼스레딩 이득이 크지 않다. 데몬(NameNode·RM·DataNode·NM·Kafka)도
코어를 쓴다.

| 태스크 슬롯 | 파싱 시간 |
|---|---|
| 4 (물리 코어만) | 3.4시간 |
| **6 (권장 시작점)** | **2.2시간** |
| 8 (vCPU 전부, 데몬과 경합) | 1.7시간 — 실제로는 더 걸릴 것 |

**슬롯 6에서 시작해 0차에서 실측한다.** 선형으로 나뉜다고 가정하지 않는다 —
팀장 의견과 같다.

### 전체

```
수집 0.6h ─► 파싱 2.2h ─► LLM 11~12h ─► 시드·검증·적재 몇 분
```

순차로 하면 **약 14시간**. 파싱이 끝난 기업부터 LLM 으로 흘려보내면(Kafka 를 두는
이유) **약 12시간**으로 준다. 어느 쪽이든 하룻밤 배치다.

**LLM 이 바닥이다.** GPU 추가는 불가하고(할당은 GPU 1 절반 고정), 동시성을 올려도
이득이 없다. 남은 길은 요청을 가볍게 하거나 모델을 낮추는 것뿐이다 —
[INFRA-DESIGN](S15P21A504-73-INFRA-DESIGN.md) 6장에 실측을 적었다.

---

## 3. Hadoop — 파싱에 둔다

### 왜 여기인가

문서 하나가 곧 독립 작업이다. 문서 사이 공유 상태가 없고 셔플이 없다. 그리고
**HDFS 가 실제로 필요하다** — 2노드가 같은 69GB 를 읽어야 하는데, 없으면 파일을
손으로 갈라 각 노드에 복사해야 한다.

### 입력을 읽는 방법 — `binaryFiles` 를 쓰지 않는다

`sc.binaryFiles` 는 파일 내용을 통째로 레코드에 담는다. 6MB × 동시 태스크 수만큼
메모리에 올라오고, 드라이버가 11,395개 경로를 먼저 나열한다. 노드 RAM 이 15GiB 라
여유가 없다.

**경로만 RDD 로 만들고 태스크가 직접 읽는다.**

```python
paths = sc.parallelize(hdfs_paths, numSlices=6 * 4)   # 슬롯 × 4
rows  = paths.mapPartitions(parse_partition)          # 태스크 안에서 WebHDFS 로 열기
```

WebHDFS(HTTP)를 쓰면 워커에 libhdfs·JVM 바인딩이 필요 없다. 이미 의존성에 있는
`requests` 로 끝난다. 6MB 파일에 HTTP 오버헤드는 무시할 수준이다.

### 산출은 Parquet

지금은 CSV 인데 워커가 한 파일에 동시 쓰기를 할 수 없다. Parquet 는 파티션 파일이
자연스럽고, 시드 만들 때 한 번만 모으면 된다.

```
HDFS  /raw/opendart/filings/annual_report/{bsns_year}/{rcept_no}.xml
      /staged/business_report/{segment,facility,main_product,rd_expense,passages}/
```

### YARN·Spark 설정 시작값

노드당 15GiB 에서 OS 1GB, DataNode 1GB, NodeManager 1GB 를 뺀다. A 는 NameNode·
ResourceManager·Kafka 로 3GB 를 더 뺀다.

| | EC2 A | EC2 B |
|---|---|---|
| `yarn.nodemanager.resource.memory-mb` | 8192 | 11264 |
| `yarn.nodemanager.resource.cpu-vcores` | 3 | 4 |

```
spark.executor.instances      3
spark.executor.cores          2
spark.executor.memory         2g
spark.executor.memoryOverhead 2g      ← PySpark 워커가 JVM 밖에서 쓴다
```

**`memoryOverhead` 를 넉넉히 준 이유**는 파싱 프로세스가 문서 하나에 약 450MB 를
쓰기 때문이다(실측). 코어 2개면 파이썬 워커 2개가 동시에 그만큼 쓴다. 기본값
(executor.memory 의 10%)으로 두면 컨테이너가 OOM 으로 죽는다.

### 파이썬 의존성

워커에 `lxml` · `PyYAML` 이 있어야 한다. venv 를 zip 으로 묶어 `--archives` 로
넘기는 방식이 가장 단순하다. 노드가 2대뿐이라 각 노드에 직접 설치해도 된다.

### 수집은 분산하지 않는다

DART **일일 20,000회 한도**가 있다. 워커를 늘리면 한도만 빨리 쓴다. 단일 노드에서
받아 `hdfs dfs -put` 한다. 이미 받아 둔 487건(2.95GB)은 다시 받지 않고 올린다.

---

## 4. Kafka — LLM 작업 큐에 둔다

### 구성

```
Spark 파싱 ──► Kafka  br.passages  (파티션 4 · replication 1)
                          │
                consumer group: llm-workers
                          ▼
              LLM 컨슈머 (동시 4) ──HTTP──► jupyter05 vLLM
                          │
                          ▼
                     br.text  ──► 시드 생성 ──► PostgreSQL
```

- **EC2 A 에 KRaft 단일 브로커.** ZooKeeper 없이 시작한다. 메시지가 11,395건 ·
  메타데이터뿐이라 브로커 하나로 충분하다. 힙 1GB 면 된다
- **파티션 4 = GPU 동시 4.** 컨슈머를 더 붙여도 GPU 가 못 받는다. 파티션 수를
  처리 능력에 맞추면 그 사실이 구조에 드러난다
- **replication 1.** 브로커가 하나라 다른 값을 줄 수 없다. 배치 작업이고 원본이
  HDFS 에 남아 있어 토픽을 잃어도 다시 만들면 된다

### 메시지에 원문을 넣지 않는다 (팀장 의견과 같음)

```json
{"corp_code":"00126380","fiscal_year":2024,"rcept_no":"20250311001085",
 "passages_path":"hdfs:///staged/business_report/passages/part-00003.parquet",
 "row_id":142}
```

구간 텍스트가 6,000자 × 2 다. 메시지에 담으면 토픽이 수백 MB 가 되고 브로커 힙
1GB 로는 부담이다. **경로 + 행 식별자만 보내고 컨슈머가 HDFS 에서 읽는다.**

### 중복은 이미 막혀 있다

컨슈머가 at-least-once 여도 `company_text` 의
UNIQUE (corp_code, fiscal_year, attr_key, seq) 가 중복을 거른다.
**at-least-once + DB UNIQUE = 사실상 한 번**이라 Kafka 에서 제일 성가신 부분이
여기서는 문제가 아니다.

### 파일 기반 체크포인트도 남긴다 (팀장 의견과 같음)

`text_llm.csv` 이어받기는 그대로 둔다. Kafka 가 없는 환경(개발 PC 단독)에서도
같은 코드가 돌아야 하고, 최종 산출·재현의 정본은 여전히 파일이다.

---

## 5. LLM 컨슈머를 어디에 두는가 — **미확인 하나**

**EC2 → jupyter05 의 vLLM(8000) 접근 가능 여부가 아직 확인되지 않았다.** 이것 하나가
컨슈머 위치를 정한다.

| | 컨슈머 위치 | 조건 |
|---|---|---|
| (가) | EC2 | EC2 → jupyter05:8000 이 열려 있어야 한다 |
| (나) | 팀 개발 PC | PC → EC2(Kafka) 와 PC → jupyter05 둘 다 필요 |

**기본값은 (나)로 둔다.** PC → jupyter05 는 이미 되는 것을 확인했고(지금까지 이걸로
487건을 돌렸다), PC → EC2 는 SSAFY 제공 장비라 열려 있을 가능성이 높다. (가)가
되면 컨슈머만 EC2 로 옮기면 되고 **구조는 그대로다** — 컨슈머는 Kafka 클라이언트 +
HTTP 클라이언트일 뿐이라 어디서 돌든 같다.

확인 명령은 이것 하나다. EC2 에서:

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 http://70.12.130.105:8000/health
```

`200` 이면 (가), 타임아웃이면 (나)다.

---

## 6. 전체 그림

```
① 수집    개발 PC ──DART API──► 로컬 ──hdfs dfs -put──► HDFS /raw/...
          단일 노드. 일일 20,000회 한도                              0.6시간

② 파싱    Spark on YARN (EC2 2노드 · 슬롯 6)
          경로 RDD → mapPartitions → WebHDFS 로 XML 읽기
          지금 파서를 그대로 호출                                    2.2시간
             └─► /staged/.../{segment,facility,main_product,rd_expense,passages}

③ 큐      passages 메타데이터 ──► Kafka br.passages (EC2 A, 파티션 4)

④ LLM     컨슈머(동시 4) ──HTTP──► jupyter05 vLLM Qwen3-32B-AWQ   11~12시간
          위치는 5장 — 기본 개발 PC, 연결되면 EC2

⑤ 시드    staged Parquet ──────────► curated/seed/*.csv             몇 분

⑥ 검증    verify_business_report.py 7축                             몇 분

⑦ 적재    COPY → PostgreSQL                                         몇 분
```

②와 ④를 겹쳐 돌리면 **약 12시간**, 순차면 **약 14시간**.

---

## 7. 지금 코드에서 바꿔야 할 것

| 단계 | 무엇 | 왜 |
|---|---|---|
| ② | 문서 1건 처리를 순수 함수로 분리 | `mapPartitions` 안에서 부르려면 파일 I/O 와 분리돼야 한다 |
| ② | WebHDFS 리더 추가 | `binaryFiles` 를 쓰지 않기로 했다 (3장) |
| ② | 산출 CSV → Parquet | 워커 동시 쓰기가 안 된다 |
| ③ | passages 를 Kafka 로 produce | 지금은 jsonl 파일 |
| ④ | `ThreadPoolExecutor(4)` + Kafka 컨슈머 | 실측 3.9배. 8은 오히려 느리다 |
| ④ | 실패 건 별도 기록 | 11,395건이면 개별 실패를 눈으로 못 쫓는다 |
| ⑤ | 시드 생성이 Parquet 를 읽게 | 지금은 `staged/business_report/*.csv` |
| 전체 | 실행 이력 테이블 | F-29(S15P21A504-36)가 원래 이 자리다 |

**검증 7축은 그대로 쓴다.** CSV 만 읽으므로 규모와 무관하다. 다만 D축이 실패 목록을
전부 출력하므로 건수가 커지면 요약 + 상위 N건으로 바꿔야 한다.

**로컬 단독 실행 경로를 없애지 않는다.** Kafka·HDFS 없이 개발 PC 에서도 같은 코드가
돌아야 파서를 고칠 때 클러스터를 띄우지 않는다. 입력·출력 위치만 설정으로 가른다.

---

## 8. 실행 순서

| 차수 | 대상 | 목적 | 예상 |
|---|---|---|---|
| **0차** | 지금 100개사 | 인프라 배선. **결과가 지금 시드와 같아야 한다** | 30분 |
| 1차 | +200개사 (누적 300) | 업종 확대 시 파싱 성공률 확인 | 1시간 |
| 2차 | +700개사 (누적 1,000) | 1차에서 늘린 패턴 검증 | 3시간 |
| 3차 | 나머지 전부 | | 6시간 |

**0차가 가장 중요하다.** 인프라를 바꾸면서 결과까지 바뀌면 Spark 때문인지 파서
때문인지 못 가린다. 지금 100개사 결과가 시드로 커밋돼 있으므로 대조할 수 있다.

```bash
# 정렬 후 비교 — Spark 산출은 파티션 순서가 다르다
sort curated/seed/segment_metric.csv > /tmp/local.csv
sort spark_out/segment_metric.csv    > /tmp/spark.csv
diff /tmp/local.csv /tmp/spark.csv && echo "동일"
```

`company_text` 의 LLM 항목은 `generated_at` 이 실행 시각이라 다르다. 그 열을 빼고
비교한다. 나머지 세 표는 결정적이라 **바이트 단위로 같아야 한다.**

각 차수 뒤에 `parse_summary.csv` 판정 분포를 보고 `patterns.yaml` 을 늘린다.
**코드가 아니라 YAML 을 늘리는 것이 원칙이다** (F-27 AC1). 지금 100개사는 매출
상위라 대기업 편향이 있고, 금융·건설·지주는 사업보고서 구조가 다르다.

---

## 9. 재현 문서로 남길 것

장비 회수 여부와 무관하게 남긴다 (팀장: 반납 안 한다고 가정하고 개발).

- Hadoop·Spark 설치와 2노드 구성 (`core-site` · `hdfs-site` · `yarn-site` 값 포함)
- Kafka KRaft 구성과 토픽·컨슈머 그룹 정의
- vLLM 실행 (`vllm-setup.sh`, 모델·GPU_MEM·MAX_LEN)
- 파이프라인 실행 순서와 각 단계 재개 방법
- 환경변수·의존성 (`.env` 키 목록, venv 배포 방식)
- 장애 후 재시작 — HDFS 는 멱등, Kafka 는 오프셋, 파일 체크포인트는 이어받기

---

## 10. 하지 말아야 할 것

- **수집을 분산하기.** DART 일일 20,000회 한도다
- **GPU 를 YARN 스케줄링에 넣기.** 태스크마다 모델을 올렸다 내리면 로딩만 1~2분이다.
  vLLM 은 상주 서버로 두고 큐로 연결한다. 팀장 방침과 같다
- **`binaryFiles` 로 6MB XML 을 레코드에 담기.** 노드 RAM 15GiB 에서 위험하다
- **`memoryOverhead` 기본값으로 두기.** PySpark 워커가 문서당 450MB 를 JVM 밖에서
  쓴다. 컨테이너가 OOM 으로 죽는다
- **원문을 Git 에 넣기.** 69GB 다. HDFS 에 두고 계보만 `manifests/` 로 남긴다
- **파서 성공률이 떨어졌다고 임계값을 푸는 것.** D축 허용오차 5%는 값이 맞는지
  가리는 유일한 장치다. 커버리지가 아쉬우면 패턴을 늘린다 (팀장 기준 4항)
- **인프라 교체와 파서 수정을 같은 차수에 하기.** 0차에서 결과가 달라지면 원인을
  못 가린다

---

## 11. 남은 확인 하나

**EC2 → jupyter05:8000 접근 가능 여부** (5장). 되면 컨슈머를 EC2 에, 안 되면 개발
PC 에 둔다. 구조는 바뀌지 않으므로 이것 때문에 설계를 멈추지 않는다.
