"""사업보고서 파싱 대상을 고른다 → `config/business_report_universe.csv`.

팀장 요청이 "기업 100개만 우선" 이고, 고르는 규칙은 **기존 13개사 고정 + 최신연도
매출 상위로 87개를 채운다** 이다 (S15P21A504-73).

기존 13개사를 고정하는 이유
---------------------------
매출 상위 100 을 그냥 잡으면 지금 데이터가 있는 13개사 중 8개사가 빠진다
(DB하이텍·한미반도체·NC·리노공업·크래프톤·넷마블·NHN·시프트업 — 실측). 그러면 셋을
동시에 잃는다.

  - `tests/fixtures/normalize/` 의 회귀 검증 기준선이 타깃 10개사에 묶여 있다
  - `curated/seed/segment_metric.csv` 190행이 이 13개사의 부문이다
  - `curated/seed/company_activity.csv` 3,409행이 타깃 10개사의 타법인 출자다

이미 검증까지 끝낸 데이터를 범위 확대 때문에 버리는 셈이라, 13개사를 먼저 넣고
나머지를 매출 순으로 채운다.

**선정 결과를 CSV 로 커밋한다.** 코드 안에만 두면 매출 시드가 갱신될 때 대상이 조용히
바뀌고, 어제 받은 원문이 오늘 목록에 없는 상태가 된다. 수집·파싱·검증이 전부 이 파일
하나를 읽는다.

    python scripts/select_business_report_universe.py                     # 100개사
    python scripts/select_business_report_universe.py --companies 300     # 1차 확대
    python scripts/select_business_report_universe.py --check             # 파일과 대조만

**앞 N개사가 집합으로 고정된다.** 300개사로 다시 골라도 앞 100개사는 지금 파일의
100개사와 같은 집합이다(실측). 매출 순위가 고정돼 있어 뒤에 붙기만 하기 때문이다.
그래서 차수를 늘려도 이미 받은 원문·산출을 다시 만들 필요가 없다.

**다만 그 100개사 안의 줄 순서는 달라질 수 있다.** 파일은 `existing_seed` 를 앞에
두는데, 그 판정이 `curated/seed` 의 현재 내용을 보기 때문이다 — 100개사를 파싱해
`segment_metric`·`company_activity` 가 늘면 다음 실행에서 `existing_seed` 도 는다
(13 → 85개사가 실제로 그랬다). 순서에 기대는 코드는 없다. `--companies N` 을 받는
쪽(`build_spark_jobs.py` · `extract_business_text_llm.py`)은 앞 N개를 잘라 **집합으로**
쓴다.
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import CONFIG, curated_seed_dir  # noqa: E402

DEFAULT_SIZE = 100          # 팀장 요청의 1차 범위. 차수를 늘릴 때는 --companies 로 준다
DEST = CONFIG / "business_report_universe.csv"

FIELDS = ["corp_code", "corp_name", "stock_code", "pick_reason",
          "revenue_rank", "revenue_year", "revenue"]


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def keep_codes(seed: Path) -> list[str]:
    """이미 데이터가 있어 빼면 안 되는 기업.

    segment_metric 13개사가 company_activity 10개사(=타깃)를 포함하므로 합집합이
    곧 segment 쪽이지만, 원천이 바뀌어도 규칙이 유지되도록 둘 다 읽어 합친다.
    """
    codes: set[str] = set()
    for name in ("segment_metric.csv", "company_activity.csv"):
        p = seed / name
        if p.exists():
            codes |= {r["corp_code"] for r in _read(p)}
    targets = CONFIG / "targets.csv"
    if targets.exists():
        codes |= {r["corp_code"] for r in _read(targets)}
    return sorted(codes)


def latest_revenue(seed: Path) -> dict[str, tuple[int, float]]:
    """corp_code → (최신 연도, 매출). 매출 행이 없는 기업은 아예 들어오지 않는다."""
    by_corp: dict[str, dict[int, float]] = collections.defaultdict(dict)
    for r in _read(seed / "company_metric.csv"):
        if r["metric_code"] != "revenue" or not r["metric_value"]:
            continue
        by_corp[r["corp_code"]][int(r["fiscal_year"])] = float(r["metric_value"])
    out = {}
    for corp, years in by_corp.items():
        y = max(years)
        out[corp] = (y, years[y])
    return out


def build(target_size: int = DEFAULT_SIZE) -> list[dict]:
    seed = curated_seed_dir()
    names = {r["corp_code"]: r for r in _read(seed / "company.csv")}
    rev = latest_revenue(seed)
    keep = keep_codes(seed)

    # 매출 내림차순 순위. 동점은 corp_code 로 갈라 실행마다 순서가 흔들리지 않게 한다.
    ranked = sorted(rev.items(), key=lambda kv: (-kv[1][1], kv[0]))
    rank = {corp: i + 1 for i, (corp, _) in enumerate(ranked)}

    picked: list[tuple[str, str]] = [(c, "existing_seed") for c in keep]
    seen = set(keep)
    for corp, _ in ranked:
        if len(picked) >= target_size:
            break
        if corp not in seen:
            picked.append((corp, "revenue_top"))
            seen.add(corp)

    rows = []
    for corp, reason in picked:
        c = names.get(corp, {})
        y, v = rev.get(corp, ("", ""))
        rows.append({
            "corp_code": corp,
            "corp_name": c.get("corp_name", ""),
            "stock_code": c.get("stock_code", ""),
            "pick_reason": reason,
            "revenue_rank": rank.get(corp, ""),
            "revenue_year": y,
            "revenue": f"{v:.0f}" if v != "" else "",
        })
    # 기존 13개사가 앞에, 나머지는 매출 순. 사람이 열어 봤을 때 규칙이 보이도록.
    rows.sort(key=lambda r: (0 if r["pick_reason"] == "existing_seed" else 1,
                             r["revenue_rank"] or 10 ** 9))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="다시 고르지 않고 파일과 대조만 한다")
    ap.add_argument("--companies", type=int, default=DEFAULT_SIZE, metavar="N",
                    help=f"고를 기업 수 (기본 {DEFAULT_SIZE}). 앞은 고정되므로 차수를 "
                         "늘릴 때 이 값만 키운다")
    args = ap.parse_args()

    rows = build(args.companies)
    if len(rows) != args.companies:
        print(f"경고: {len(rows)}개사만 골랐다 (목표 {args.companies}). "
              "company_metric 의 revenue 커버리지를 확인하라", file=sys.stderr)

    if args.check:
        if not DEST.exists():
            print(f"{DEST} 가 없다", file=sys.stderr)
            return 1
        old = [r["corp_code"] for r in _read(DEST)]
        new = [r["corp_code"] for r in rows]
        if old == new:
            print(f"일치 — {len(new)}개사")
            return 0
        print(f"불일치: 파일 {len(old)}개사, 다시 고른 결과 {len(new)}개사", file=sys.stderr)
        for c in sorted(set(new) - set(old)):
            print(f"  + {c}", file=sys.stderr)
        for c in sorted(set(old) - set(new)):
            print(f"  - {c}", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with DEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    kept = sum(1 for r in rows if r["pick_reason"] == "existing_seed")
    print(f"{len(rows)}개사 → {DEST}")
    print(f"  기존 시드 보유 {kept}개사 + 매출 상위 {len(rows) - kept}개사")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
