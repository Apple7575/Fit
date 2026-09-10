# hadoop

DART 원본(raw)을 담고 정규화를 분산 처리하기 위한 2노드 클러스터.
**인프라 상태·접속 정보 문서다.** 원본 적재·`RawStore` 교체·Spark 잡 작성 등
파이프라인 쪽 작업은 데이터 파트 영역이며 여기서 다루지 않는다.

## 구성

| 노드 | 주소 | 사설 IP | 역할 |
|---|---|---|---|
| `ha-master` | `j15a504a.p.ssafy.io` | 172.26.6.113 | NameNode · SecondaryNameNode · ResourceManager · DataNode · NodeManager |
| `ha-worker1` | `j15a504.p.ssafy.io` | 172.26.13.212 | DataNode 만 |

```
Hadoop 3.3.6 · Spark 3.5.9 · Java 11
/opt/hadoop · /opt/spark · /opt/venv-data       데이터·로그 /opt/hadoop-data
HDFS 용량 517.86GB (노드당 50GB 예약 제외)
```

**1호기(`ha-worker1`)에는 NodeManager 를 두지 않는다.** 거기서 executor 가 돌면
prod·dev·Jenkins 와 메모리를 다퉈 서비스가 죽는다. 저장(DataNode)만 맡긴다.
`/opt/venv-data` 도 2호기에만 있어, 이 배치가 곧 "executor 가 패키지 없는 노드에
뜨는" 사고의 안전장치다.

## 현재 상태 (09-10 실측)

| 항목 | 상태 |
|---|---|
| 데몬 | 2호기 5종(NameNode·SecondaryNameNode·ResourceManager·DataNode·NodeManager) / 1호기 DataNode |
| DataNode | Live 2, 복제 2 |
| NodeManager | `YARN Total Nodes:1` (ha-master) |
| Spark on YARN | 검증됨 (SparkPi SUCCEEDED) |
| executor python | `/opt/venv-data` — lxml·PyYAML·python-dotenv·requests·psycopg import 확인 |
| raw | 비어 있음 |
| staged | 비어 있음 |
| curated/seed | 시드 CSV 7종 |
| 재부팅 | 자동 기동 없음 — 아래 명령으로 수동 기동 |

## 기동·정지

`conf/workers` 는 DataNode 와 NodeManager 를 동시에 제어한다. 두 대에 DataNode 를 두면서
NodeManager 는 한 대만 띄우려면 YARN 기동 때 대상을 좁힌다.

```bash
ssh -i J15A504T.pem ubuntu@j15a504a.p.ssafy.io

start-dfs.sh                                    # DataNode 양 노드
HADOOP_WORKER_NAMES=ha-master start-yarn.sh     # NodeManager 는 2호기만  ★

HADOOP_WORKER_NAMES=ha-master stop-yarn.sh
stop-dfs.sh
```

`start-yarn.sh` 를 그냥 실행하면 **1호기에도 NodeManager 가 뜬다.** 반드시 앞의 변수를 붙인다.

## 상태 확인

```bash
jps                        # 2호기 5개 / 1호기 DataNode 1개
hdfs dfsadmin -report      # Live datanodes (2)
yarn node -list            # Total Nodes:1
hdfs fsck /                # Status: HEALTHY
```

## 웹 UI — 공인 IP 로 열지 않았다

`9870`·`8088` 은 인터넷에 노출하지 않는다. SSH 터널로만 본다.

```bash
ssh -i J15A504T.pem -L 9870:localhost:9870 -L 8088:localhost:8088 ubuntu@j15a504a.p.ssafy.io
```

`http://localhost:9870` (HDFS) · `http://localhost:8088` (YARN)

## HDFS 경로·내용

`data/docs/DATA_STORAGE_STANDARD.md` 2장의 3계층을 그대로 옮겼다.

```
/data
├── raw/                                  비어 있음
│   ├── opendart/api/                     정형 API 응답 JSON
│   ├── opendart/filings/annual_report/   사업보고서 원문 XML
│   └── google_news_rss/articles/
├── staged/{opendart,business_report,google_news_rss}/   비어 있음
└── curated/seed/                         시드 CSV 7종
/spark-logs                               Spark 이벤트 로그
```

curated 시드 (`git` 의 `data/curated/seed/` 를 md5 대조해 업로드, 7종 일치):

| 파일 | 행수 |
|---|---|
| `company.csv` | 2,704 |
| `company_activity.csv` | 4,829 |
| `company_metric.csv` | 58,647 |
| `company_text.csv` | 11,204 |
| `industry.csv` | 78 |
| `metric.csv` | 16 |
| `segment_metric.csv` | 1,235 |

## 데이터 파트 참고 — HDFS 입출력

원본을 넣고 빼는 명령만 둔다. 무엇을 언제 올릴지·잡 작성은 데이터 파트가 정한다.

올리기:

```bash
hdfs dfs -put <로컬>/fnlttSingl*.json <로컬>/empSttus_*.json  /data/raw/opendart/api/
hdfs dfs -put <로컬>/document_*.xml                          /data/raw/opendart/filings/annual_report/
```

내리기 — 파이프라인은 `.cache/` 를 **평면 폴더**로 읽는다. `api` 와 `filings` 를 **둘 다** 받는다
(`api` 만 받으면 R&D 원문 XML 이 빠져 R&D 가 `not_found`):

```bash
hdfs dfs -get /data/raw/opendart/api/*                    <로컬캐시>/
hdfs dfs -get /data/raw/opendart/filings/annual_report/*  <로컬캐시>/
```

`hdfs dfs -put` 은 원자적이지 않다. 끊기면 잘린 파일이 남으므로 올린 뒤 md5 로 대조한다
(`md5sum <로컬>` vs `hdfs dfs -cat <경로> | md5sum`).

## 파이프라인 연결 지점

파이프라인 코드는 데이터 파트 소유다 (`data/`, 구조는 `data/docs/DESIGN.md` 6장 「파이프라인 구조」).
이 클러스터와는 세 지점에서 만난다:

- **원본 입출력** — HDFS `/data/raw/...` (위 「데이터 파트 참고」)
- **실행 환경** — executor python `/opt/venv-data` (아래 「접속·설정 정보」)
- **잡 제출** — `spark-submit --master yarn`

## 접속·설정 정보

| 항목 | 값 |
|---|---|
| NameNode RPC | `hdfs://ha-master:9000` |
| NameNode HTTP (WebHDFS) | `http://ha-master:9870` |
| ResourceManager | `ha-master:8088` |
| HDFS 사용자 | `ubuntu` |
| Spark master | `yarn` |
| executor python | `/opt/venv-data/bin/python` (`spark.pyspark.python` 에 설정됨) |

## 알아둘 것 (운영 제약)

**포트는 사설망에만 열려 있다.** ufw 가 상대 노드 IP 전체를 허용하고, 인터넷에는 22 번만
열려 있다. 하둡은 포트를 수십 개 쓰므로 포트별로 여는 대신 IP 단위로 허용했다.

**`dfs.datanode.du.reserved = 50GB`.** 1호기는 postgres·Docker 와 같은 파티션을 쓴다.
이걸 두지 않으면 HDFS 가 디스크를 채워 **운영 DB 쓰기를 실패시킬 수 있다.**

**executor 메모리 상한.** `yarn.scheduler.maximum-allocation-mb = 6144` 이므로
`spark.executor.memory` + `memoryOverhead` 가 6144MB 를 넘으면 컨테이너 요청이 거부된다.

**`yarn.log-aggregation-enable = true`.** 끄면 잡이 끝나는 순간 컨테이너 로그가 사라져
`yarn logs` 로도 못 본다.

**HDFS 휴지통은 껐다** (`fs.trash.interval = 0`). `hdfs dfs -rm -r` 은 즉시 삭제다.

## 구성 파일

`conf/` — core-site · hdfs-site · yarn-site · mapred-site · hadoop-env · workers
`setup-node.sh`(하둡) · `setup-spark.sh`(Spark·venv) · `verify-pyspark.py`(executor import 검증)

## 남은 인프라 작업

- [ ] systemd 유닛 — 재부팅 시 자동 기동
- [ ] 데몬 감시 — 헬스체크 cron 에 `jps` 확인 추가
