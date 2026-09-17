"""raw → staged. 원본 RSS 를 표준 컬럼으로 정제한다.

    python scripts/stage_news.py                 # raw 의 모든 수집 실행
    python scripts/stage_news.py --run <run_id>   # 하나만

네트워크를 쓰지 않는다. `data/raw/google_news_rss/articles/` 의 XML 만 읽는다.
같은 원본으로 다시 돌리면 같은 결과가 나온다 (scripts/verify_news.py 13번이 대조한다).

기간(KST)은 `run.json` → CLI → 요청 계획 도출 순으로 정한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.news import corpmap, rawstore, stage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", dest="runs", help="수집 실행 ID. 여러 번 줄 수 있다")
    parser.add_argument("--target-start", help="KST 시작일. run.json 값을 덮어쓴다")
    parser.add_argument("--target-end", help="KST 종료일, exclusive")
    args = parser.parse_args()

    run_ids = args.runs or rawstore.list_runs()
    if not run_ids:
        print("정제할 원본이 없다.")
        print(f"  기대 경로: {rawstore.RAW_DIR.relative_to(rawstore.ROOT.parent)}/<collection_run_id>/*.xml")
        print("  수집기 출력 폴더가 있으면 scripts/import_news_raw.py --from <폴더> 로 먼저 들여온다.")
        return 0

    mapper = corpmap.load()
    print(f"기업 색인  config/company_universe.csv {mapper.row_count}건")
    failures = 0
    for run_id in run_ids:
        run = rawstore.load_run(run_id)
        run_json = run.directory / "run.json"
        start = args.target_start or ""
        end = args.target_end or ""
        if run_json.exists() and not (start and end):
            recorded = json.loads(run_json.read_text(encoding="utf-8"))
            start = start or recorded.get("target_start", "")
            end = end or recorded.get("target_end_exclusive", "")
        result = stage.stage_run(run, mapper, start, end)
        paths = stage.write(result)
        summary = result.summary
        print(f"\n[{run_id}]  {summary['target_start']} ~ {summary['target_end_exclusive']} (exclusive)")
        print(f"  원본 관측 {summary['raw_observations']} → 기간내 {summary['in_window_observations']}"
              f" → 대표 {summary['staged_rows']} (중복 {summary['duplicate_rows']}, 제외 {summary['rejected_rows']})")
        print(f"  기업 매핑  성공 {summary['staged_rows'] - summary['unresolved_corp_rows']}"
              f" / 실패 {summary['unresolved_corp_rows']} {summary['corp_map_reasons'] or ''}")
        print(f"  발행시각   파싱 {summary['published_at_parsed']} / 실패 {summary['published_at_unparsed']}")
        if summary["reject_reasons"]:
            print(f"  제외 사유  {summary['reject_reasons']}")
        if summary["raw_checksum_mismatches"]:
            failures += 1
            print(f"  실패: 원본 체크섬 불일치 {summary['raw_checksum_mismatches']}")
        expected = summary["collector_target_observations"]
        if expected is not None and expected != summary["in_window_observations"]:
            failures += 1
            print(f"  실패: 수집기 집계 {expected} ≠ 정제 기간내 {summary['in_window_observations']}")
        if summary["collector_saturated_queries"]:
            print(f"  주의: 조회 포화 가능 쿼리 {len(summary['collector_saturated_queries'])}건 — 전수 수집 보장 없음")
        print(f"  → {paths['articles'].relative_to(rawstore.ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
