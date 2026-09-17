"""전 종목 재무 수치 원천 검산 — DB·API 불필요.

`staged/opendart/financials.csv` 만 읽는다. **착지 테이블이 아직 없어도 돌아간다** —
85번이 착지 대기 중에 검산부터 편입한 것과 같다. 적재를 거치지 않는 검산이 하나
있어야 적재 버그와 원천 문제를 구분할 수 있다.

판정은 86번과 같이 두 단계다.

    차이   임계 초과. **기록 대상이지 오류가 아니다** (회사 기재 방식 차이일 수 있다)
    모순   물리적으로 불가능. 이것만 오류다

축
--
    F-1  자산총계 = 부채총계 + 자본총계          모순
    F-2  유동 + 비유동 = 총계 (자산·부채)        차이 — 금융업은 유동/비유동을 나누지 않는다
    F-3  Y년 응답의 전기 = Y-1년 응답의 당기      차이 — 소급 재작성이 정상적으로 일어난다
    F-4  같은 계정 중복 행의 값이 갈리는가         모순
    F-5  상식 (자산총계 음수 · 영업이익 > 매출액)  음수는 모순, 나머지는 차이

F-1 임계를 상대값으로 잡은 이유
------------------------------
절대 1,000원으로 자르면 안 된다. 천원 단위로 공시하는 회사가 ±1,000원씩 어긋나는데
(실측 6건) 그건 반올림이고, 같은 1,000원이 작은 회사에서는 진짜 오류다.
**상대 0.01% 와 절대 1,000원을 둘 다 넘을 때만** 모순으로 센다 — 실측에서 이 경계가
반올림 6건과 진짜 4건을 정확히 갈랐다.

    python scripts/verify_financials.py
    python scripts/verify_financials.py -v      # 차이도 전부 출력
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from pipeline.paths import CONFIG, staged_dir  # noqa: E402

# F-1 임계. 둘 다 넘어야 모순이다 (모듈 주석 참고).
IDENTITY_REL = 0.0001        # 0.01%
IDENTITY_ABS = 1_000         # 원

# F-3 소급 재작성은 흔하다. 일치 비율이 이 밑으로 떨어지면 수집이 깨진 것이다.
CROSSYEAR_MIN_OK = 0.90


def load_known() -> set[tuple[str, int, str]]:
    """확인을 마친 발견 사항. 새로 생긴 것만 실패로 세기 위한 기준선이다."""
    p = CONFIG / "known_findings.yaml"
    if not p.exists():
        return set()
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {(c["corp_code"], int(c["year"]), c["axis"])
            for c in (doc.get("contradictions") or [])}


class Result:
    def __init__(self) -> None:
        self.ok = 0
        self.diffs: list[str] = []
        self.contradictions: list[tuple[str, str, tuple]] = []

    def diff(self, msg: str) -> None:
        self.diffs.append(msg)

    def contra(self, msg: str, key: tuple) -> None:
        self.contradictions.append((msg, msg, key))


def num(s: str) -> float | None:
    return float(s) if s else None


def main() -> int:
    ap = argparse.ArgumentParser(description="전 종목 재무 수치 원천 검산")
    ap.add_argument("-v", "--verbose", action="store_true", help="차이도 전부 출력")
    args = ap.parse_args()

    src = staged_dir() / "financials.csv"
    if not src.exists():
        print(f"없음: {src} — scripts/normalize_financials.py 를 먼저 돌려라")
        return 127
    rows = list(csv.DictReader(src.open(encoding="utf-8")))

    names: dict[str, str] = {}
    up = CONFIG / "company_universe.csv"
    if up.exists():
        names = {r["corp_code"]: r["corp_name"]
                 for r in csv.DictReader(up.open(encoding="utf-8-sig"))}

    known = load_known()

    # (corp_code, year, fs_div) -> {account_nm: 당기값}
    acct: dict[tuple, dict[str, float]] = defaultdict(dict)
    dup_conflict = 0
    cur: dict[tuple, float | None] = {}
    prev: dict[tuple, float | None] = {}
    for r in rows:
        k = (r["corp_code"], r["bsns_year"], r["fs_div"])
        v = num(r["thstrm_amount"])
        if v is not None:
            prior = acct[k].get(r["account_nm"])
            if prior is not None and prior != v:
                dup_conflict += 1
            acct[k][r["account_nm"]] = v
        ck = (r["corp_code"], r["fs_div"], r["sj_div"], r["account_nm"])
        cur[(ck, int(r["bsns_year"]))] = v
        prev[(ck, int(r["bsns_year"]))] = num(r["frmtrm_amount"])

    print("=" * 74)
    print(f"전 종목 재무 수치 원천 검산 — {len(rows):,}행 · "
          f"회사 {len({k[0] for k in acct}):,}")
    print("=" * 74)

    def label(code: str) -> str:
        return f"{names.get(code, code)[:14]}({code})"

    # ── F-1 회계 항등식 ────────────────────────────────────────────
    f1 = Result()
    for k, a in acct.items():
        if not all(x in a for x in ("자산총계", "부채총계", "자본총계")):
            continue
        d = a["자산총계"] - a["부채총계"] - a["자본총계"]
        base = max(abs(a["자산총계"]), 1)
        if abs(d) < IDENTITY_ABS or abs(d) / base < IDENTITY_REL:
            f1.ok += 1
            continue
        code, year, fs = k
        msg = (f"{label(code):26} {year} {fs}  자산 {a['자산총계']:>18,.0f}  "
               f"차이 {d:>18,.0f} ({abs(d) / base:.2%})")
        f1.contra(msg, (code, int(year), "F-1"))

    # ── F-2 부분합 ────────────────────────────────────────────────
    f2 = Result()
    for k, a in acct.items():
        for parts, total in ((("유동자산", "비유동자산"), "자산총계"),
                             (("유동부채", "비유동부채"), "부채총계")):
            if not all(x in a for x in (*parts, total)):
                continue
            d = a[parts[0]] + a[parts[1]] - a[total]
            if abs(d) < IDENTITY_ABS or abs(d) / max(abs(a[total]), 1) < IDENTITY_REL:
                f2.ok += 1
            else:
                f2.diff(f"{label(k[0]):26} {k[1]} {k[2]}  {total}  차이 {d:>18,.0f}")

    # ── F-3 연도 교차 ─────────────────────────────────────────────
    f3_checked = f3_ok = 0
    for (ck, y), v in prev.items():
        c = cur.get((ck, y - 1))
        if v is None or c is None:
            continue
        f3_checked += 1
        if abs(v - c) < 1:
            f3_ok += 1
    f3_rate = (f3_ok / f3_checked) if f3_checked else 0.0

    # ── F-5 상식 ─────────────────────────────────────────────────
    f5 = Result()
    for k, a in acct.items():
        if a.get("자산총계", 0) < 0:
            f5.contra(f"{label(k[0]):26} {k[1]} {k[2]}  자산총계 음수 "
                      f"{a['자산총계']:,.0f}", (k[0], int(k[1]), "F-5"))
        if "영업이익" in a and "매출액" in a and a["영업이익"] > a["매출액"]:
            f5.diff(f"{label(k[0]):26} {k[1]} {k[2]}  영업이익 > 매출액 "
                    f"({a['영업이익']:,.0f} > {a['매출액']:,.0f})")
        else:
            f5.ok += 1

    # ── 출력 ─────────────────────────────────────────────────────
    def rate(ok: int, tot: int) -> str:
        return f"{ok / tot:.4%}" if tot else "—"

    f1_tot = f1.ok + len(f1.contradictions)
    f2_tot = f2.ok + len(f2.diffs)
    print(f"\n  F-1  자산 = 부채 + 자본        대상 {f1_tot:>7,} · "
          f"성립 {f1.ok:>7,} ({rate(f1.ok, f1_tot)}) · 모순 {len(f1.contradictions)}")
    print(f"  F-2  유동 + 비유동 = 총계      대상 {f2_tot:>7,} · "
          f"성립 {f2.ok:>7,} ({rate(f2.ok, f2_tot)}) · 차이 {len(f2.diffs)}")
    print(f"  F-3  연도 교차                 대상 {f3_checked:>7,} · "
          f"성립 {f3_ok:>7,} ({f3_rate:.4%}) · 차이 {f3_checked - f3_ok:,}")
    print(f"  F-4  중복 행 값 일치           갈린 것 {dup_conflict}")
    print(f"  F-5  상식                      모순 {len(f5.contradictions)} · "
          f"차이 {len(f5.diffs)}")

    if dup_conflict:
        f5.contra(f"중복 행의 값이 {dup_conflict}건 갈렸다 — 정규화가 접으면 안 된다",
                  ("*", 0, "F-4"))

    new_contra = [c for c in (f1.contradictions + f5.contradictions)
                  if c[2] not in known]
    old_contra = [c for c in (f1.contradictions + f5.contradictions)
                  if c[2] in known]

    if f1.contradictions or f5.contradictions:
        print("\n" + "-" * 74)
        print("모순 (물리적으로 불가능 — 이것만 오류다)")
        print("-" * 74)
        for msg, _, key in old_contra:
            print(f"  [확인됨] {msg}")
        for msg, _, key in new_contra:
            print(f"  [신규]   {msg}")

    n_diff = len(f2.diffs) + (f3_checked - f3_ok) + len(f5.diffs)
    print("\n" + "-" * 74)
    print(f"차이 ({n_diff:,}건) — 회사 기재 방식·소급 재작성일 수 있다. "
          f"기록 대상이지 오류가 아니다")
    print("-" * 74)
    print(f"  F-2 부분합       {len(f2.diffs):>6,}  금융업은 유동/비유동을 나누지 않는다")
    print(f"  F-3 연도 교차    {f3_checked - f3_ok:>6,}  소급 재작성")
    print(f"  F-5 영업이익     {len(f5.diffs):>6,}  영업이익 > 매출액")
    if args.verbose:
        for m in f2.diffs[:50] + f5.diffs[:50]:
            print("      " + m)

    # ── 판정 ─────────────────────────────────────────────────────
    print("\n" + "=" * 74)
    fail = bool(new_contra) or f3_rate < CROSSYEAR_MIN_OK
    if f3_rate < CROSSYEAR_MIN_OK:
        print(f"판정: 연도 교차 일치율 {f3_rate:.2%} < {CROSSYEAR_MIN_OK:.0%} — "
              f"수집이 깨졌을 수 있다")
    if new_contra:
        print(f"판정: 새로 생긴 모순 {len(new_contra)}건 — 확인 필요 "
              f"(확인을 마친 것 {len(old_contra)}건은 세지 않았다)")
    if not fail:
        print(f"판정: 새로 생긴 모순 0건 "
              f"(확인을 마친 것 {len(old_contra)}건은 세지 않았다)")
    print("=" * 74)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
