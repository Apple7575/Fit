"""Spark 산출(Parquet) 을 대조용 CSV 로 내린다 (S15P21A504-73 0차).

    spark-submit --master yarn scripts/spark_dump_parquet_csv.py \
        --src hdfs:///data/staged/business_report/spark \
        --ref staged/business_report \
        --out ~/spark_out_csv

왜 필요한가
----------
`compare_parse_output.py` 는 CSV 를 읽고 **헤더가 같아야** 대조에 들어간다. Spark
잡은 dict 로 DataFrame 을 만들어서 열이 알파벳 순으로 서고, 로컬 산출과 순서가
다르다 — 값이 전부 같아도 "헤더가 다르다"로 떨어진다. 그래서 기준 산출(`--ref`)의
헤더 순서를 그대로 가져다 쓴다.

**드라이버에서 파이썬 `csv` 로 쓴다.** Spark 의 CSV 라이터를 쓰면 따옴표 처리와
개행 표현이 로컬 실행기와 달라, 값이 같아도 대조가 깨진다. 0차는 "값이 같은가"를
보는 것이라 쓰는 방식까지 같아야 한다. 487건 규모는 드라이버 한 대로 충분하다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# 대조 도구가 읽는 이름 그대로. passages 만 JSONL 이다.
CSV_NAMES = ("segment_revenue", "facility", "main_product", "rd_expense", "parse_summary")
PASSAGE_KEYS = ("corp_code", "fiscal_year", "rcept_no", "business", "rd")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Spark 산출 루트 (HDFS)")
    ap.add_argument("--ref", type=Path, required=True,
                    help="기준 산출 디렉터리. 헤더 순서를 여기서 읽는다")
    ap.add_argument("--out", type=Path, required=True, help="CSV 를 내릴 로컬 디렉터리")
    args = ap.parse_args()

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("business-report-dump").getOrCreate()
    args.out.mkdir(parents=True, exist_ok=True)
    bad = 0

    for name in CSV_NAMES:
        ref = args.ref / f"{name}.csv"
        if not ref.exists():
            print(f"[  ] {name:<16} 기준 파일 없음 — 건너뜀")
            continue
        with ref.open(encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f))

        try:
            df = spark.read.parquet(f"{args.src.rstrip('/')}/{name}")
        except Exception as e:                                  # noqa: BLE001
            print(f"[✗] {name:<16} Parquet 를 못 읽었다: {type(e).__name__}")
            bad += 1
            continue

        missing = [c for c in header if c not in df.columns]
        extra = [c for c in df.columns if c not in header]
        if missing or extra:
            # 열 구성이 다르면 값 대조가 무의미하다. 여기서 잡아야 compare 가
            # "헤더가 다르다" 한 줄만 뱉고 끝나는 상황을 피한다.
            print(f"[✗] {name:<16} 열 구성이 기준과 다르다 — 없는 열 {missing} · 남는 열 {extra}")
            bad += 1
            continue

        dest = args.out / f"{name}.csv"
        n = 0
        with dest.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for row in df.select(*header).toLocalIterator():
                w.writerow(["" if v is None else v for v in row])
                n += 1
        print(f"[OK] {name:<16} {n:,}행 → {dest}")

    # passages 는 대조 도구가 다루지 않는다. 건수·문자 수만 재서 PHASE0 1장의
    # 합격 기준("건수와 문자 수가 같아야 한다")을 확인할 수 있게 같이 내린다.
    try:
        df = spark.read.parquet(f"{args.src.rstrip('/')}/passages")
    except Exception:                                            # noqa: BLE001
        print("[  ] passages         Parquet 없음 — 건너뜀")
        df = None
    if df is not None:
        dest = args.out / "passages.jsonl"
        n = chars = 0
        with dest.open("w", encoding="utf-8", newline="\n") as f:
            for row in df.select(*PASSAGE_KEYS).toLocalIterator():
                d = {k: row[k] for k in PASSAGE_KEYS}
                chars += len(d.get("business") or "") + len(d.get("rd") or "")
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                n += 1
        print(f"[OK] passages         {n:,}건 · 본문 {chars:,}자 → {dest}")

    spark.stop()
    print()
    print("내려받기 완료" if not bad else f"열 구성이 어긋난 산출 {bad}종 — 위를 보라")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
