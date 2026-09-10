"""로컬 `.cache/document_*.xml` 을 HDFS 로 올리는 명령을 만든다 (S15P21A504-73 0차).

    python scripts/hdfs_put_business_reports.py --jobs _out/spark_jobs.csv \
        --out _out/hdfs_put.sh
    bash _out/hdfs_put.sh          # EC2 에서 실행

**직접 올리지 않고 스크립트를 만든다.** 개발 PC 에 hdfs 클라이언트가 없고, 파일이
EC2 로 먼저 가야 한다. 무엇을 올릴지 정하는 일(연도별 경로·중복 제거)만 여기서
하고 실행은 클러스터 쪽에 맡긴다.

이미 받아 둔 487건(2.95GB)은 다시 내려받지 않는다. 그게 0차의 입력이다.

`-f` 를 쓰지 않는다
------------------
`hdfs dfs -put -f` 는 덮어쓴다. 원문은 불변이라 덮어쓸 일이 없고(저장 기준 1장),
덮어쓰기를 허용하면 잘못된 파일을 조용히 밀어 넣는 경로가 생긴다. 이미 있으면
건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import ROOT, cache_dir  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=Path, default=ROOT / "_out" / "spark_jobs.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "_out" / "hdfs_put.sh")
    ap.add_argument("--local-root", default="$HOME/br_raw",
                    help="EC2 에서 원문이 놓일 위치 (scp 로 먼저 옮긴 곳)")
    args = ap.parse_args()

    with args.jobs.open(encoding="utf-8-sig", newline="") as f:
        jobs = list(csv.DictReader(f))

    cache = cache_dir()
    have, missing = [], []
    for j in jobs:
        src = cache / f"document_{j['rcept_no']}.xml"
        (have if src.exists() else missing).append(j)

    years = sorted({j["fiscal_year"] for j in have})
    lines = [
        "#!/usr/bin/env bash",
        "# scripts/hdfs_put_business_reports.py 가 만든 파일이다. 직접 고치지 마라.",
        "# EC2 에서 실행한다. 원문은 먼저 scp 로 --local-root 에 옮겨 둔다.",
        "set -euo pipefail",
        "",
        f"LOCAL_ROOT={args.local_root}",
        "",
        "# 연도별 디렉터리. 파일이 11,395개까지 늘어도 한 디렉터리에 몰리지 않는다.",
    ]
    lines += [f"hdfs dfs -mkdir -p /raw/opendart/filings/annual_report/{y}" for y in years]
    lines += ["", "put() {", "  # 이미 있으면 건너뛴다 — 원문은 불변이라 덮어쓸 일이 없다",
              '  if hdfs dfs -test -e "$2"; then echo "skip $2"; else hdfs dfs -put "$1" "$2"; fi',
              "}", ""]
    for j in have:
        rel = j["hdfs_path"].replace("hdfs://", "", 1)
        if not rel.startswith("/"):
            rel = "/" + rel.split("/", 1)[1]
        lines.append(f'put "$LOCAL_ROOT/document_{j["rcept_no"]}.xml" "{rel}"')
    lines += ["", 'echo "완료 — $(hdfs dfs -count /raw/opendart/filings/annual_report)"']

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    total = sum((cache / f"document_{j['rcept_no']}.xml").stat().st_size for j in have)
    print(f"올릴 원문 {len(have):,}건 · {total / 1e9:.2f}GB → {args.out}")
    print(f"  연도 {', '.join(years)}")
    if missing:
        print(f"  로컬에 없는 원문 {len(missing):,}건 — "
              f"scripts/collect_business_reports.py 를 먼저 돌려라")
    print()
    print("EC2 로 옮기는 예:")
    print(f"  rsync -av --include='document_*.xml' --exclude='*' \\")
    print(f"    {cache}/ ubuntu@<EC2-A>:{args.local_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
