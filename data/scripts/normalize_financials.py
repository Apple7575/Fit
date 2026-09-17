"""전 종목 수치 데이터 정규화 — raw → staged.

**API 를 호출하지 않는다.** manifest 가 가리키는 원본만 읽는다.

manifest 기준으로 읽는 이유: `raw/opendart/api/` 를 glob 으로 훑으면 실측·스모크
테스트가 남긴 파일이 섞인다. 실제로 섞였다 — 정렬 전 묶음으로 받아둔 2023 파일
하나가 2,388행을 더 얹었다. **원본 디렉터리는 수집 실행 단위가 아니다.**

하는 일

  ① 금액 문자열 → 수 (콤마·괄호음수·△·결측 '-' 는 text.to_num 이 처리)
  ② 당기순이익(손실) 중복 행 접기 — 실측상 회사·fs_div 마다 정확히 2행이고
     159/159 값이 같았다. 그래도 **값이 갈리면 접지 않고 경고로 남긴다**
  ③ 통화 · 결산기준일 이상을 표시 (KRW 가 아닌 회사가 있다)
  ④ 연도 교차 검산 — Y년 응답의 전기값 = Y-1년 응답의 당기값

④ 가 이 스크립트의 검산 축이다. 같은 값을 서로 다른 해의 응답에서 두 번 받으므로
적재를 거치지 않고도 원천 정합성을 볼 수 있다 (86번이 쓴 방식과 같은 결).

    python scripts/normalize_financials.py
    python scripts/normalize_financials.py --run-id a7e332adadb3
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.normalize.text import to_num
from pipeline.paths import manifest_dir, raw_api_dir, staged_dir

OUT_FIELDS = [
    "corp_code", "stock_code", "bsns_year", "reprt_code", "fs_div", "fs_nm",
    "sj_div", "sj_nm", "account_nm", "currency",
    "thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount",
    "thstrm_dt", "rcept_no", "ord",
]

# 정규 계정 15종. 실측(100개사)에서 이 밖의 계정은 6건뿐이었다 — 금융·특수업종.
CORE_BS = ("유동자산", "비유동자산", "자산총계", "유동부채", "비유동부채",
           "부채총계", "자본금", "이익잉여금", "자본총계")
CORE_IS = ("매출액", "영업이익", "법인세차감전 순이익", "당기순이익(손실)", "총포괄손익")


def latest_manifest() -> Path:
    files = sorted(manifest_dir().glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit("manifest 가 없다 — scripts/collect_financials.py 를 먼저 돌려라")
    return files[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", help="생략하면 가장 최근 실행")
    args = ap.parse_args()

    mpath = (manifest_dir() / f"{args.run_id}.json") if args.run_id else latest_manifest()
    man = json.loads(mpath.read_text(encoding="utf-8"))
    reprt = man["reprt_code"]
    print(f"실행 {man['collection_run_id']} · 연도 {man['연도']} · 묶음 {man['묶음']}")

    raw = raw_api_dir()
    records: list[dict] = []
    missing = 0
    for year in man["연도"]:
        for b in man["batches"]:
            p = raw / f"fnlttMultiAcnt_{year}_{reprt}_{b['digest']}.json"
            if not p.exists():
                missing += 1
                continue
            for r in json.loads(p.read_text(encoding="utf-8")).get("list") or []:
                records.append(r)
    if missing:
        print(f"  경고: 원본 {missing}개 없음")
    print(f"원본 {len(records):,}행")

    # ── ② 중복 접기 ────────────────────────────────────────────────
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        grouped[(r.get("corp_code"), r.get("bsns_year"), r.get("fs_div"),
                 r.get("sj_div"), r.get("account_nm"))].append(r)

    folded = conflicts = 0
    conflict_rows: list[dict] = []
    out: list[dict] = []
    for key, rs in grouped.items():
        if len(rs) > 1:
            vals = {to_num(x.get("thstrm_amount")) for x in rs}
            if len(vals) == 1:
                folded += len(rs) - 1
            else:
                conflicts += 1
                conflict_rows.append({
                    "corp_code": key[0], "bsns_year": key[1], "fs_div": key[2],
                    "account_nm": key[4], "값": " / ".join(str(v) for v in sorted(
                        vals, key=lambda x: (x is None, x))),
                })
                # 값이 갈리면 접지 않는다. 전부 남겨 사람이 판단한다.
                for x in rs:
                    out.append(x)
                continue
        out.append(rs[0])

    # ── ①③ 변환과 이상 표시 ─────────────────────────────────────────
    staged_rows: list[dict] = []
    currency = Counter()
    odd_dt = Counter()
    for r in out:
        currency[r.get("currency")] += 1
        dt = (r.get("thstrm_dt") or "")
        if "현재" in dt and not dt.startswith(f"{r.get('bsns_year')}.12.31"):
            odd_dt[r.get("corp_code")] += 1
        staged_rows.append({
            "corp_code": r.get("corp_code"), "stock_code": r.get("stock_code"),
            "bsns_year": r.get("bsns_year"), "reprt_code": r.get("reprt_code"),
            "fs_div": r.get("fs_div"), "fs_nm": r.get("fs_nm"),
            "sj_div": r.get("sj_div"), "sj_nm": r.get("sj_nm"),
            "account_nm": r.get("account_nm"), "currency": r.get("currency"),
            "thstrm_amount": to_num(r.get("thstrm_amount")),
            "frmtrm_amount": to_num(r.get("frmtrm_amount")),
            "bfefrmtrm_amount": to_num(r.get("bfefrmtrm_amount")),
            "thstrm_dt": dt, "rcept_no": r.get("rcept_no"), "ord": r.get("ord"),
        })

    # ── ④ 연도 교차 검산 ────────────────────────────────────────────
    cur: dict[tuple, float | None] = {}
    prev: dict[tuple, float | None] = {}
    for r in staged_rows:
        k = (r["corp_code"], r["fs_div"], r["sj_div"], r["account_nm"])
        y = int(r["bsns_year"])
        cur[(k, y)] = r["thstrm_amount"]
        prev[(k, y)] = r["frmtrm_amount"]

    checked = agree = 0
    disagree_rows: list[dict] = []
    for (k, y), v in prev.items():
        c = cur.get((k, y - 1))
        if v is None or c is None:
            continue
        checked += 1
        if abs(v - c) < 1:
            agree += 1
        else:
            # 자르지 않는다. 500건에서 끊으면 파일만 본 사람이 불일치를 500건으로
            # 읽는다 — 실제로는 11,984건이었다.
            disagree_rows.append({"corp_code": k[0], "fs_div": k[1],
                                  "account_nm": k[3], "연도": y,
                                  f"{y}응답_전기": v, f"{y-1}응답_당기": c,
                                  "차이": v - c})

    # ── 산출 ──────────────────────────────────────────────────────
    d = staged_dir()
    fpath = d / "financials.csv"
    with fpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(staged_rows)

    issues = d / "financials_issues.csv"
    with issues.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["종류", "corp_code", "연도", "fs_div", "account_nm", "내용"])
        for c in conflict_rows:
            w.writerow(["중복값_불일치", c["corp_code"], c["bsns_year"],
                        c["fs_div"], c["account_nm"], c["값"]])
        for r in disagree_rows:
            w.writerow(["연도교차_불일치", r["corp_code"], r["연도"], r["fs_div"],
                        r["account_nm"], f"차이 {r['차이']:,.0f}"])
        for code, n in odd_dt.most_common():
            w.writerow(["결산기준일_12월아님", code, "", "", "", f"{n}행"])
        for r in staged_rows:
            if r["currency"] and r["currency"] != "KRW":
                w.writerow(["통화_KRW아님", r["corp_code"], r["bsns_year"],
                            r["fs_div"], r["account_nm"], r["currency"]])

    companies = len({r["corp_code"] for r in staged_rows})
    print(f"\n중복 접기      {folded:,}행 · 값이 갈린 것 {conflicts}건")
    print(f"staged 행      {len(staged_rows):,} · 회사 {companies:,}")
    print(f"통화           {dict(currency.most_common())}")
    print(f"결산기준일 이상  {len(odd_dt)}개사")
    print(f"\n[검산] 연도 교차 (Y응답의 전기 = Y-1응답의 당기)")
    print(f"  대조 {checked:,}쌍 · 일치 {agree:,} "
          f"({agree / checked:.3%}) · 불일치 {checked - agree:,}")
    print(f"\n→ {fpath}\n→ {issues}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
