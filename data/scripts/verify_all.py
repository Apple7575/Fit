"""전체 검증 실행 (S15P21A504-86 Step 5).

    python scripts/verify_all.py
    python scripts/verify_all.py --skip-api     # 백엔드를 못 띄우는 환경
    python scripts/verify_all.py -v

검증이 네 갈래로 흩어져 있어 하나씩 기억해서 돌려야 했다. 다음 사람이 하나만
돌리면 되게 묶는다. **종료코드로 성공/실패를 알린다** — 사람이 출력을 읽지
않아도 CI 나 스크립트가 판단할 수 있어야 한다.

무엇을 덮는가
-----------
    [1] 정규화 회귀   verify_normalize.py   기준선 150건.       DB 불필요 · API 불필요
    [2] 원천 -> DB    verify_db.py          329/329, 139/139.  DB 필요
    [3] 원천 정합성   verify_source.py      검산 6축.           DB 필요
    [4] DB -> API     verify_api.py         3,449건.           DB 필요 · 응답 원본 필요
    [5] 누락 사유     report_gaps.py        리포트. 판정하지 않는다
    [6] 전 종목 재무  verify_financials.py  검산 5축.           DB 불필요 · API 불필요

    ① 원천 ↔ ② DB ↔ ③ API 3자 대조가 [2]+[4] 로 완결된다 (F-30).

의존성이 다르다
------------
[1] 은 `.cache/` 만 있으면 된다. [2][3] 은 DB 가, [4] 는 그 위에 API 응답
원본까지 필요하다. 그래서 앞이 실패해도 뒤를 건너뛰지 않고 **각각 독립으로**
돌린다 — 어디까지 되는지 알아야 원인을 좁힐 수 있다.

[6] 은 `staged/opendart/financials.csv` 만 읽는다. **착지 테이블이 없어도
돌아간다** — 적재를 거치지 않는 검산이 하나 있어야 적재 버그와 원천 문제를
구분할 수 있다. 착지가 끝나도 이 경로는 남긴다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# (표시 이름, 스크립트, 인자, 판정에 넣을지)
STEPS = [
    ("정규화 회귀 (기준선 150건)", "verify_normalize.py", [], True),
    ("원천 → DB", "verify_db.py", ["--report"], True),
    ("원천 정합성 검산", "verify_source.py", [], True),
    ("DB → API 노출값", "verify_api.py", [], True),
    ("누락 사유 분류", "report_gaps.py", ["--csv"], False),
    ("전 종목 재무 원천 검산", "verify_financials.py", [], True),
]


def run_one(name: str, script: str, args: list[str], verbose: bool) -> tuple[int, str, float]:
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(HERE / script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), time.monotonic() - t0


def tail(text: str, n: int) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join("      " + ln for ln in lines[-n:])


def main() -> int:
    ap = argparse.ArgumentParser(description="전체 검증 실행")
    ap.add_argument("--skip-api", action="store_true",
                    help="DB → API 대조를 건너뛴다 (백엔드를 못 띄우는 환경)")
    ap.add_argument("-v", "--verbose", action="store_true", help="각 단계 전체 출력")
    args = ap.parse_args()

    print("=" * 74)
    print("전체 검증")
    print("=" * 74)

    results: list[tuple[str, int, float, bool]] = []
    for name, script, extra, counts in STEPS:
        if args.skip_api and script == "verify_api.py":
            print(f"\n  건너뜀  {name}  (--skip-api)")
            continue
        if not (HERE / script).exists():
            print(f"\n  없음    {name}  ({script})")
            results.append((name, 127, 0.0, counts))
            continue

        code, out, secs = run_one(name, script, extra, args.verbose)
        mark = "통과" if code == 0 else "실패"
        print(f"\n  [{mark}] {name}   ({secs:.1f}s, 종료코드 {code})")
        print(tail(out, 40 if args.verbose else 6))
        results.append((name, code, secs, counts))

    print("\n" + "=" * 74)
    judged = [r for r in results if r[3]]
    failed = [r for r in judged if r[1] != 0]
    for name, code, secs, counts in results:
        badge = "  -  " if not counts else ("통과" if code == 0 else "실패")
        print(f"  {badge}  {name:<28} {secs:>5.1f}s")
    print("=" * 74)

    if failed:
        print(f"\n실패 {len(failed)}건: " + ", ".join(n for n, *_ in failed))
        return 1
    print("\n전부 통과")
    print("범위: 원천 ↔ DB ↔ API 3자 대조 완결 (F-30)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
