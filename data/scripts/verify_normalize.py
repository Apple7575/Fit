"""정규화 회귀 검증 (WP-6 완료 판정).

초기 검증에서 확정한 결과 JSON 을 기준선으로 삼아, 정식 파이프라인이 **같은 값을
내는지** 대조한다. 값이 하나라도 달라지면 규칙을 옮기는 과정에서 뭔가 흘린 것이다.

    tests/fixtures/normalize/step22_results.json   매출·영업이익·R&D  50건
    tests/fixtures/normalize/step25_results.json   직원 3종           50건

기준선의 기업 구성은 현재 `config/targets.csv` 와 다르다(NAVER·카카오·한미반도체가
있고 LG전자·NHN·시프트업이 없다). 검증은 기준선 기준으로 돌린다 — 규칙이 그대로
옮겨졌는지를 보는 것이 목적이기 때문이다.

    python scripts/verify_normalize.py
    python scripts/verify_normalize.py -v      # 불일치 상세
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.normalize.employee import aggregate  # noqa: E402
from pipeline.normalize.revenue import apply_backcalc, resolve  # noqa: E402
from pipeline.normalize.rnd import from_document  # noqa: E402
from pipeline.paths import ROOT  # noqa: E402
from pipeline.rawstore import RawMissing, RawStore  # noqa: E402

BASELINE = ROOT / "tests" / "fixtures" / "normalize"
VERBOSE = "-v" in sys.argv


def close(a, b, tol=1e-6) -> bool:
    """둘 다 없으면 일치. 하나만 없으면 불일치. 수는 상대오차로 비교."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale <= tol


def check_financials(store: RawStore) -> tuple[int, int, Counter]:
    base = json.loads((BASELINE / "step22_results.json").read_text(encoding="utf-8"))
    ok = bad = 0
    verdicts = Counter()
    for b in base:
        got = resolve(store, b["corp_code"], b["bsns_year"])
        # 경로 D(R&D 역산)는 기준선에도 반영되어 있다. 같은 조건으로 맞춘다
        if b.get("rnd_krw") and b.get("ratio_reported"):
            apply_backcalc(got, b["rnd_krw"], b["ratio_reported"], b.get("ratio_decimals"))
        verdicts[got.revenue_verdict] += 1
        diffs = []
        for field, mine, theirs in (
            ("revenue", got.revenue, b["revenue"]),
            ("operating_profit", got.operating_profit, b["operating_profit"]),
            ("fs_div", got.fs_div, b["fs_div"]),
            ("revenue_verdict", got.revenue_verdict, b["revenue_verdict"]),
            ("revenue_source", got.revenue_source, b["revenue_source"]),
            ("revenue_worst_gap_pct", got.revenue_worst_gap_pct,
             b.get("revenue_worst_gap_pct")),
            ("backcalc_gap_pct", got.backcalc_gap_pct, b.get("backcalc_gap_pct")),
        ):
            if not close(mine, theirs):
                diffs.append(f"{field}: {mine!r} != {theirs!r}")
        if diffs:
            bad += 1
            print(f"  FAIL {b['corp_name']} {b['bsns_year']}")
            for d in diffs:
                print(f"       {d}")
        else:
            ok += 1
    return ok, bad, verdicts


def check_rnd(store: RawStore) -> tuple[int, int, Counter]:
    base = json.loads((BASELINE / "step22_results.json").read_text(encoding="utf-8"))
    ok = bad = 0
    verdicts = Counter()
    for b in base:
        if not b.get("rcept_no"):
            continue
        try:
            path = store.document(b["rcept_no"])
        except RawMissing as e:
            bad += 1
            print(f"  FAIL {b['corp_name']} {b['bsns_year']} — {e}")
            continue
        got = from_document(path, b["revenue"])
        verdicts[got.verdict] += 1
        diffs = []
        for field, mine, theirs in (
            ("verdict", got.verdict, b["verdict"]),
            ("rnd_krw", got.rnd_krw, b.get("rnd_krw")),
            ("unit", got.unit, b.get("unit")),
            ("table_idx", got.table_idx, b.get("table_idx")),
            ("ratio_reported", got.ratio_reported, b.get("ratio_reported")),
        ):
            if not close(mine, theirs):
                diffs.append(f"{field}: {mine!r} != {theirs!r}")
        if diffs:
            bad += 1
            print(f"  FAIL {b['corp_name']} {b['bsns_year']}")
            for d in diffs:
                print(f"       {d}")
        else:
            ok += 1
    return ok, bad, verdicts


def check_employee(store: RawStore) -> tuple[int, int, Counter]:
    base = json.loads((BASELINE / "step25_results.json").read_text(encoding="utf-8"))
    ok = bad = 0
    warns = Counter()
    for b in base:
        rows = store.emp_status(b["corp_code"], b["bsns_year"])
        got = aggregate(rows, b["corp_code"], b["bsns_year"])
        warns["warnings" if got.warnings else "clean"] += 1
        diffs = []
        for field, mine, theirs in (
            ("employee_count", got.employee_count, b["employee_count"]),
            ("regular_count", got.regular_count, b["regular_count"]),
            ("contract_count", got.contract_count, b["contract_count"]),
            ("avg_salary_krw", got.avg_salary_krw, b["avg_salary_krw"]),
            ("avg_tenure_years", got.avg_tenure_years, b["avg_tenure_years"]),
            ("salary_source", got.salary_source, b["salary_source"]),
        ):
            if not close(mine, theirs, tol=1e-9):
                diffs.append(f"{field}: {mine!r} != {theirs!r}")
        if diffs:
            bad += 1
            print(f"  FAIL {b['corp_name']} {b['bsns_year']}")
            for d in diffs:
                print(f"       {d}")
        else:
            ok += 1
    return ok, bad, warns


def main() -> int:
    store = RawStore()
    total_bad = 0

    print("[1] 매출·영업이익 (기준선 step22_results.json)")
    ok, bad, verdicts = check_financials(store)
    print(f"  {ok}/{ok + bad} 일치   판정 {dict(verdicts)}")
    total_bad += bad

    print("\n[2] R&D (기준선 step22_results.json)")
    ok, bad, verdicts = check_rnd(store)
    print(f"  {ok}/{ok + bad} 일치   판정 {dict(verdicts)}")
    total_bad += bad

    print("\n[3] 직원 3종 (기준선 step25_results.json)")
    ok, bad, warns = check_employee(store)
    print(f"  {ok}/{ok + bad} 일치   {dict(warns)}")
    total_bad += bad

    print(f"\n{'통과' if total_bad == 0 else f'불일치 {total_bad}건'}")
    return 1 if total_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
