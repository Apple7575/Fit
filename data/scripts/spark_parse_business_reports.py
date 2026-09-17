"""Spark 파싱 잡 — HDFS 원문 → staged Parquet (S15P21A504-73 0차).

    spark-submit --master yarn --deploy-mode client \
        --conf spark.executor.instances=1 \
        --conf spark.executor.cores=2 \
        --conf spark.executor.memory=2g \
        --conf spark.executor.memoryOverhead=3g \
        --conf spark.executorEnv.PYTHONPATH=/home/ubuntu/pipeline/data \
        scripts/spark_parse_business_reports.py \
            --jobs hdfs:///data/staged/business_report/jobs.csv \
            --out  hdfs:///data/staged/business_report/spark \
            --webhdfs http://ha-master:9870 --slices 8

executor 자원이 위 값인 이유
--------------------------
NodeManager 가 한 대뿐이고(`ha-master`) YARN 에 6,144MB 만 주어져 있다. client
모드의 AM 이 1,024MB 를 먹으므로 executor 컨테이너는 5,120MB 하나가 최대다.
`instances=3` 으로 두면 하나만 뜨고 둘은 영영 pending 이다. vcore 도 3개 중
AM 이 하나를 써서 `cores=2` 가 상한이다.

배분을 클러스터 기본값 `4g + 1g` 이 아니라 `2g + 3g` 로 뒤집는 이유는 PySpark
때문이다 — 파싱은 JVM 밖 파이썬 프로세스가 하고 문서 하나에 약 450MB 를 쓴다.
`cores=2` 면 파이썬 워커 둘이 동시에 그만큼 쓰므로 그 몫이 memoryOverhead 로
가야 한다.

executor 가 `pipeline` 패키지를 찾는 법
------------------------------------
드라이버의 `sys.path` 조작은 executor 에 전해지지 않는다. 태스크 안에서
`pipeline.business_report.extract` 를 import 하므로 executor 쪽 `PYTHONPATH` 가
코드를 가리켜야 한다 — 없으면 `ModuleNotFoundError: No module named 'pipeline'`
로 태스크가 전부 죽는다(실측).

`--py-files pipeline.zip` 으로 보내면 안 된다. `pipeline.patterns` 가
`config/patterns.yaml` 을 **패키지 위치 기준으로** 찾기 때문에 zip 안에서는 못
찾는다. 지금은 CD(Jenkins `Deploy-Data`)가 `data/` 를 NodeManager 노드에 통째로
두므로 그 경로를 PYTHONPATH 로 준다. **NodeManager 를 늘리면 그 노드에도 같은
배포가 있어야 한다.**

**파싱 로직이 여기 없다.** `pipeline.business_report.extract.parse_one` 을 부른다.
로컬 실행(`scripts/parse_business_reports.py`)과 같은 함수라, 0차의 전제인
"인프라를 바꿔도 결과가 같다" 를 확인할 수 있다.

`binaryFiles` 를 쓰지 않는 이유
------------------------------
`sc.binaryFiles` 는 6MB 파일을 통째로 레코드에 담고 드라이버가 경로 11,395개를 먼저
나열한다. EC2 노드가 15GiB 라 여유가 없다. 대신 **경로만 RDD 로 만들고 태스크가
WebHDFS 로 직접 읽는다.** 워커에 libhdfs·JVM 바인딩이 필요 없고 이미 의존성에 있는
`requests` 로 끝난다.

memoryOverhead 를 크게 잡는 이유
------------------------------
파싱 프로세스가 문서 하나에 약 450MB 를 쓴다(실측). PySpark 파이썬 워커는 JVM 밖에서
돌아 executor.memory 가 아니라 memoryOverhead 를 먹는다. 기본값(10%)이면 컨테이너가
OOM 으로 죽는다. cores=2 면 파이썬 워커 2개가 동시에 그만큼 쓴다.

입력
----
`--jobs` 는 (corp_code, fiscal_year, rcept_no, corp_name, external_revenue, hdfs_path)
컬럼을 가진 Parquet 다. `scripts/build_spark_jobs.py` 가 만든다 — 접수번호 매핑과
매출 대조값을 드라이버에서 미리 붙여 두면 태스크가 큰 CSV 를 읽지 않아도 된다.
"""
from __future__ import annotations

import argparse
import os
import sys

# 드라이버가 pipeline 패키지를 찾게 한다. executor 쪽은 이 조작이 닿지 않아
# spark.executorEnv.PYTHONPATH 로 따로 준다 (위 docstring).
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

WEBHDFS_TIMEOUT = 120


def _read_hdfs(path: str, webhdfs: str, user: str) -> bytes:
    """WebHDFS 로 파일 하나를 읽는다. 태스크 안에서 돈다.

    NameNode 가 DataNode 로 리다이렉트하므로 `allow_redirects=True` 가 필요하다.
    큰 파일이라 timeout 을 넉넉히 준다.
    """
    import requests

    rel = path.replace("hdfs://", "", 1)
    if "/" in rel and not rel.startswith("/"):
        rel = "/" + rel.split("/", 1)[1]
    url = f"{webhdfs.rstrip('/')}/webhdfs/v1{rel}"
    r = requests.get(url, params={"op": "OPEN", "user.name": user},
                     allow_redirects=True, timeout=WEBHDFS_TIMEOUT)
    r.raise_for_status()
    return r.content


def make_partition_fn(webhdfs: str, user: str):
    """파티션 하나를 처리하는 함수. 클로저로 설정만 싸서 워커에 보낸다.

    patterns 는 **파티션마다 한 번만** 읽는다. 문서마다 YAML 을 다시 파싱하면
    11,395번 읽게 된다.
    """
    def run(rows):
        from pipeline.business_report import extract as ex
        from pipeline.patterns import patterns

        p = patterns()
        for row in rows:
            d = row.asDict() if hasattr(row, "asDict") else dict(row)
            try:
                raw = _read_hdfs(d["hdfs_path"], webhdfs, user)
            except Exception as e:                     # noqa: BLE001
                yield {"kind": "summary",
                       "row": {"corp_code": d["corp_code"],
                               "corp_name": d.get("corp_name", ""),
                               "fiscal_year": d["fiscal_year"],
                               "rcept_no": d["rcept_no"], "bytes": "",
                               "error": f"read: {type(e).__name__}: {e}"[:200]}}
                continue

            # 대조 매출은 숫자여야 한다. 작업 목록이 CSV·Parquet 를 거치면서
            # 문자열이 되는데, 그대로 넘기면 부문 합계 대조가
            # `TypeError: unsupported operand type(s) for -: 'float' and 'str'`
            # 로 죽는다(실측). 로컬 실행기는 float|None 을 넘기므로 여기서 맞춘다 —
            # 타입이 다르면 "같은 함수를 부른다"는 0차의 전제가 깨진다.
            ext = d.get("external_revenue")
            if isinstance(ext, str):
                ext = float(ext) if ext.strip() else None

            res = ex.parse_one(
                raw, corp_code=d["corp_code"], fiscal_year=int(d["fiscal_year"]),
                rcept_no=d["rcept_no"], corp_name=d.get("corp_name", ""),
                external_revenue=ext,
                size_bytes=len(raw), p=p)

            for r in res.segments:
                yield {"kind": "segment", "row": r}
            for r in res.facilities:
                yield {"kind": "facility", "row": r}
            for r in res.products:
                yield {"kind": "product", "row": r}
            if res.rnd:
                yield {"kind": "rnd", "row": res.rnd}
            if res.passages:
                yield {"kind": "passages", "row": res.passages}
            yield {"kind": "summary", "row": res.summary}
    return run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True,
                    help="작업 목록 경로. .csv 면 CSV, 아니면 Parquet 로 읽는다")
    ap.add_argument("--out", required=True, help="산출 루트 (HDFS)")
    ap.add_argument("--webhdfs", default=os.environ.get(
        "WEBHDFS_URL", "http://localhost:9870"), help="NameNode WebHDFS 주소")
    ap.add_argument("--user", default=os.environ.get("HDFS_USER", "ubuntu"))
    ap.add_argument("--slices", type=int, default=24,
                    help="파티션 수. 태스크 슬롯의 3~4배가 무난하다")
    args = ap.parse_args()

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("business-report-parse").getOrCreate()
    sc = spark.sparkContext

    # build_spark_jobs.py 가 내놓는 것이 CSV 다. Parquet 로 한 번 옮기는 단계를
    # 두면 그 변환 자체가 또 하나의 실패 지점이 된다 — 확장자로 갈라 그냥 읽는다.
    if args.jobs.endswith(".csv"):
        jobs = spark.read.option("header", True).csv(args.jobs)
    else:
        jobs = spark.read.parquet(args.jobs)
    n = jobs.count()
    print(f"작업 {n:,}건 · 파티션 {args.slices}")

    # 파티션을 슬롯보다 넉넉히 나눈다. 문서 크기가 1MB~14MB 로 고르지 않아
    # 파티션이 적으면 큰 문서가 몰린 태스크가 꼬리를 만든다.
    out = (jobs.repartition(args.slices).rdd
           .mapPartitions(make_partition_fn(args.webhdfs, args.user))
           .cache())

    # 여기서 한 번에 물리게 한다. 이 줄이 없으면 아래 루프의 첫 `isEmpty()` 가
    # **파티션 하나만** 계산하면서 나머지 슬롯을 놀린다 — 487건 실측에서 그 한
    # 파티션에 3분 48초가 단독으로 들었다(전체 22분 중). 전부 한꺼번에 계산해
    # 캐시에 올려두면 그 뒤 루프는 캐시만 읽는다.
    produced = out.count()
    print(f"산출 행 {produced:,} — 캐시 적재 완료")

    # 산출 종류별로 갈라 쓴다. Parquet 는 워커마다 파일이 생기는 것이 자연스럽고,
    # 시드 만들 때 한 번만 모은다 — CSV 로 쓰면 동시 쓰기가 깨진다.
    for kind, name in (("segment", "segment_revenue"), ("facility", "facility"),
                       ("product", "main_product"), ("rnd", "rd_expense"),
                       ("passages", "passages"), ("summary", "parse_summary")):
        rows = out.filter(lambda x, k=kind: x["kind"] == k).map(lambda x: x["row"])
        if rows.isEmpty():
            print(f"  {name:<16} 0행 — 건너뜀")
            continue
        df = spark.createDataFrame(rows.map(lambda r: {k: (str(v) if v is not None else "")
                                                       for k, v in r.items()}))
        dest = f"{args.out.rstrip('/')}/{name}"
        df.write.mode("overwrite").parquet(dest)
        print(f"  {name:<16} {df.count():,}행 → {dest}")

    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
