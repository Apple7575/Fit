"""시드 행수가 직전보다 급감하면 **쓰기 전에** 멈춘다.

검증은 시드에 *들어간* 행만 본다. 그래서 값이 통째로 사라지면
`verify_business_report.py` 7축이 "5/7 통과" 를 그대로 내놓는다 — 커지는 오류는
눈에 띄고 작아지는 쪽은 안 보인다는 것을 세 번 겪었다 (외화 단위표를 원화로 읽어
1억 배가 된 것은 한눈에 걸렸고, 단위 띄어쓰기로 100만분의 1이 된 것과 표 행 병합으로
부문매출 24%가 사라진 것은 못 잡았다). **파싱이 조용히 값을 잃었는지는 직전 시드와의
행수 대조로만 드러난다.**

기준은 `manifests/seed/<table>.json` 이고, Git 추적이라 곧 '머지된 시드' 다.
계보는 CSV 를 쓴 **뒤에** 갱신되므로 여기서 멈추면 기준도 그대로 남는다 — 한 번
줄어든 값이 다음 기준이 되는 미끄럼이 없다.

**막는 것이 목적이 아니라 모르고 지나가지 않게 하는 것이 목적이다.** 줄어드는 것이
맞는 수정도 있다 (헤더 오파싱을 걷어내며 시설투자가 3,747 → 3,578 이 됐다).
그때는 `--allow-shrink` 로 지나간다.

    from pipeline import seed_guard
    seed_guard.add_arguments(parser)
    ...
    seed_guard.check(table, rows, manifest_dir=..., fields=...,
                     max_drop=args.max_drop, allow_shrink=args.allow_shrink)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# 직전 시드보다 이 비율을 넘게 줄면 멈춘다.
MAX_DROP = 0.05
# 이보다 작은 무리는 보지 않는다 — 몇 행짜리는 정상 변동에도 비율이 크게 흔들린다.
MIN_BASE = 50
# 비율과 무관하게 이 행수 안쪽의 감소는 통과시킨다.
MIN_ROWS = 5

# 표마다 '무엇이 몇 행인지' 를 가르는 칸. **표 전체 행수만 보면 한 갈래가 통째로
# 빠져도 비율이 묽어진다** — 부문매출 6,391행(−24%)이 segment_metric 전체로는
# −13% 였다 (docs/S15P21A504-SEGMENT-TABLE-REGRESSION.md).
KIND_COLUMN = {
    "company_metric": "metric_code",
    "segment_metric": "metric_code",
    "company_activity": "activity_type",
    "company_text": "attr_key",
}


def _say(line: str) -> None:
    """콘솔이 cp949 라도 죽지 않는다 — 멈추는 순간의 출력이 가장 중요하다.

    부르는 쪽이 stdout 을 utf-8 로 돌려놓는 것에 기대지 않는다. '✖'·'⚠' 는
    cp949 에 없어서, 그대로 두면 급감을 알리다가 UnicodeEncodeError 로 죽는다.
    """
    try:
        print(line)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(line.encode(enc, "replace").decode(enc, "replace"))


def add_arguments(parser) -> None:
    """시드를 만드는 스크립트들이 같은 두 옵션을 갖게 한다."""
    parser.add_argument("--allow-shrink", action="store_true",
                        help="직전 시드보다 행이 줄어도 쓴다 (줄어드는 것이 맞는 수정일 때)")
    parser.add_argument("--max-drop", type=float, default=MAX_DROP, metavar="비율",
                        # argparse 가 help 를 % 서식으로 한 번 더 돌린다 — %% 로 적는다
                        help=f"행수 감소 허용선 (기본 {MAX_DROP * 100:g}%%)")


def breakdown(table: str, rows: list[dict]) -> dict[str, int]:
    """표를 갈래별 행수로 쪼갠다. 갈래 칸이 없는 표는 빈 dict 다."""
    col = KIND_COLUMN.get(table)
    if not col:
        return {}
    return dict(sorted(Counter(str(r.get(col, "") or "") for r in rows).items()))


def previous(table: str, manifest_dir: Path) -> dict | None:
    """직전 시드의 계보. 없거나 못 읽으면 None 이다."""
    path = Path(manifest_dir) / f"{table}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _say(f"  ⚠ {table}: 직전 계보를 못 읽었다 ({e}) — 행수 대조를 건너뛴다")
        return None


def drops(before: dict[str, int], after: dict[str, int],
          max_drop: float) -> list[tuple[str, int, int]]:
    """허용선을 넘어 줄어든 항목. 사라진 갈래는 after 가 0 이라 여기서 걸린다."""
    out = []
    for name, prev in before.items():
        if not isinstance(prev, int) or prev < MIN_BASE:
            continue
        now = after.get(name, 0)
        if prev - now > max(prev * max_drop, MIN_ROWS):
            out.append((name, prev, now))
    return out


def check(table: str, rows: list[dict], *, manifest_dir: Path,
          fields: list[str] | None = None, max_drop: float = MAX_DROP,
          allow_shrink: bool = False) -> None:
    """급감이면 `SystemExit` 로 멈춘다. 부르는 쪽은 **쓰기 전에** 부른다."""
    prev = previous(table, manifest_dir)
    if prev is None:
        _say(f"  · {table}: 직전 계보가 없어 행수 대조를 건너뛴다")
        return

    kind = KIND_COLUMN.get(table, "갈래")
    before: dict[str, int] = {"전체 행": prev.get("seed_rows", 0)}
    if "distinct_corp_codes" in prev:
        before["기업 수"] = prev["distinct_corp_codes"]
    before.update({f"{kind}={k}": v
                   for k, v in (prev.get("row_breakdown") or {}).items()})

    after: dict[str, int] = {"전체 행": len(rows)}
    if fields is None or "corp_code" in fields:
        codes = {r["corp_code"] for r in rows if "corp_code" in r}
        if codes or not rows:
            after["기업 수"] = len(codes)
    after.update({f"{kind}={k}": v for k, v in breakdown(table, rows).items()})

    found = drops(before, after, max_drop)
    if not found:
        return

    _say(f"  {'⚠' if allow_shrink else '✖'} {table}: 직전 시드보다 줄었다 "
         f"(허용선 {max_drop:.0%})")
    for name, prev_n, now_n in found:
        _say(f"      {name}: {prev_n:,} → {now_n:,} ({(now_n - prev_n) / prev_n:+.1%})")
    if allow_shrink:
        _say("      --allow-shrink 라 그대로 쓴다")
        return
    raise SystemExit(
        f"\n{table} 시드를 쓰지 않고 멈췄다. 직전 CSV 와 계보는 그대로다.\n"
        "줄어든 것이 맞는 수정이면 --allow-shrink 를 붙이고, 아니면 산출을 직전\n"
        "것과 대조하라 — 사업보고서는 scripts/compare_parse_output.py 가 문서\n"
        "단위로 보여 주고, 뉴스는 staged 가 다 있는지부터 본다.")
