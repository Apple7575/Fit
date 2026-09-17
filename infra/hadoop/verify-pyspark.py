"""executor 에서 파이프라인 의존 패키지가 import 되는지 확인한다.

드라이버에서 되는 것은 의미가 없다 — 실패는 항상 executor 에서 난다.

    spark-submit --master yarn infra/hadoop/verify-pyspark.py
"""
from pyspark.sql import SparkSession

MODULES = ("lxml.etree", "yaml", "requests", "dotenv", "psycopg")


def probe(_):
    import os
    import socket
    import sys

    result = {
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "python": sys.version.split()[0],
    }
    for mod in MODULES:
        try:
            __import__(mod)
            result[mod] = "OK"
        except Exception as exc:
            result[mod] = f"실패({type(exc).__name__})"
    return [result]


spark = SparkSession.builder.appName("infra-pyspark-probe").getOrCreate()
rows = spark.sparkContext.parallelize(range(24), 8).mapPartitions(probe).collect()
spark.stop()

seen = []
for row in rows:
    key = (row["host"], row["python"]) + tuple(row[m] for m in MODULES)
    if key not in seen:
        seen.append(key)

print("\n=== executor 검증 결과 ===")
for host, py, *states in seen:
    print(f"  {host}  python {py}")
    for mod, state in zip(MODULES, states):
        print(f"      {mod:<12} {state}")

failed = [k for k in seen if any(s != "OK" for s in k[2:])]
print(f"\n  executor 조합 {len(seen)}개 · 실패 {len(failed)}개")
raise SystemExit(1 if failed else 0)
