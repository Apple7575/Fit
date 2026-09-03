"""DB ↔ API 노출값 대조 (S15P21A504-86 Step 2 / F-30 의 마지막 칸).

    python scripts/verify_api.py
    python scripts/verify_api.py -v      # 불일치 상세

3자 대조의 세 번째다.

    ① 원천(DART 응답)  ↔ ② DB      scripts/verify_db.py    (84 에서 완료)
    ② DB              ↔ ③ API     이 스크립트

**API 를 호출하지 않는다.** `scripts/probe_backend_api.py` 가 받아둔
`tests/fixtures/api/` 를 읽는다. 대조 규칙을 고쳤을 때 API 를 다시 때리지
않기 위해서다 — DART 수집·정규화를 분리한 것과 같은 이유다.

응답이 오래됐으면 probe 를 먼저 다시 돌려라.

대조 규칙은 짐작하지 않고 백엔드 코드에서 확인했다
------------------------------------------------
    scaled()      value.setScale(value_scale, HALF_UP)
    toYoy()       전년 행이 없으면 yoy 자체가 null
    changeRate()  당년 값이 없거나 전년 값이 0 이하면 null
                  아니면 (당년-전년) x 100 / 전년, HALF_UP
"""
from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect  # noqa: E402
from pipeline.paths import ROOT  # noqa: E402

VERBOSE = "-v" in sys.argv
FIX = ROOT / "tests" / "fixtures" / "api"
CHANGE_RATE_SCALE = 1          # 백엔드 CHANGE_RATE_SCALE 과 같아야 한다


def scaled(value, scale: int):
    """백엔드 scaled() 와 같은 규칙. NUMERIC → 표시 자릿수."""
    if value is None:
        return None
    q = Decimal(1).scaleb(-scale)
    return Decimal(value).quantize(q, rounding=ROUND_HALF_UP)


def change_rate(cur, prev):
    """백엔드 changeRate() 와 같은 규칙."""
    if cur is None or prev is None or Decimal(prev) <= 0:
        return None
    q = Decimal(1).scaleb(-CHANGE_RATE_SCALE)
    return ((Decimal(cur) - Decimal(prev)) * 100 / Decimal(prev)).quantize(
        q, rounding=ROUND_HALF_UP)


def eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return Decimal(str(a)) == Decimal(str(b))


class Report:
    def __init__(self):
        self.checked = 0
        self.fails: list[str] = []

    def check(self, cond: bool, msg: str):
        self.checked += 1
        if not cond:
            self.fails.append(msg)

    def section(self, title: str):
        print(f"\n{title}")

    def done(self, label: str):
        bad = len(self.fails)
        print(f"    {self.checked - bad}/{self.checked} 통과" +
              (f"   불일치 {bad}건" if bad else ""))
        for f in self.fails[: (None if VERBOSE else 5)]:
            print(f"      FAIL {f}")
        if not VERBOSE and bad > 5:
            print(f"      ... 외 {bad - 5}건 (-v 로 전체 보기)")


def load(name: str) -> dict | None:
    p = FIX / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fixtures(prefix: str):
    for p in sorted(FIX.glob(f"{prefix}*.json")):
        yield p.stem, json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 지표 대조

def check_metrics(conn, rep: Report) -> None:
    """metrics 응답의 값·자릿수·yoy·비활성 지표 제외를 대조한다."""
    with conn.cursor() as cur:
        cur.execute("""SELECT corp_code, fiscal_year, metric_code, metric_value
                         FROM company_metric""")
        db = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}
        cur.execute("SELECT metric_code, value_scale, name_ko, unit, is_active FROM metric")
        cat = {r[0]: {"scale": r[1], "label": r[2], "unit": r[3], "active": r[4]}
               for r in cur.fetchall()}

    active = {k for k, v in cat.items() if v["active"]}
    inactive = {k for k, v in cat.items() if not v["active"]}

    for name, fx in fixtures("metrics_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            continue
        data = body["data"]
        corp, year = data["corpCode"], data["year"]
        keys = [m["key"] for m in data["metrics"]]

        # 비활성 지표(rd_cost)는 응답에 없어야 한다
        for code in inactive:
            rep.check(code not in keys, f"{name}: 비활성 지표 {code} 가 응답에 있다")
        # 활성 지표는 값이 없어도 자리가 유지되어야 한다
        rep.check(set(keys) == active,
                  f"{name}: 지표 구성이 다르다 {sorted(set(keys) ^ active)}")

        for m in data["metrics"]:
            code = m["key"]
            meta = cat.get(code)
            if meta is None:
                rep.check(False, f"{name}: 카탈로그에 없는 지표 {code}")
                continue
            want = scaled(db.get((corp, year, code)), meta["scale"])
            rep.check(eq(want, m["value"]),
                      f"{name} {code}: DB {want} != API {m['value']}")
            rep.check(m["label"] == meta["label"],
                      f"{name} {code}: label {m['label']} != {meta['label']}")
            rep.check(m["unit"] == meta["unit"],
                      f"{name} {code}: unit {m['unit']} != {meta['unit']}")

            # yoy — 전년 행이 없으면 yoy 자체가 null
            prev_raw = db.get((corp, year - 1, code))
            prev = scaled(prev_raw, meta["scale"])
            yoy = m.get("yoy")
            if fx["_request"]["params"].get("yoy") == "false":
                rep.check(yoy is None, f"{name} {code}: yoy=false 인데 yoy 가 있다")
                continue
            if prev is None:
                rep.check(yoy is None, f"{name} {code}: 전년 값이 없는데 yoy 가 있다")
            else:
                rep.check(yoy is not None, f"{name} {code}: 전년 값이 있는데 yoy 가 없다")
                if yoy:
                    rep.check(eq(prev, yoy.get("prevValue")),
                              f"{name} {code}: prevValue {yoy.get('prevValue')} != DB {prev}")
                    want_rate = change_rate(want, prev)
                    rep.check(eq(want_rate, yoy.get("changeRate")),
                              f"{name} {code}: changeRate {yoy.get('changeRate')} != {want_rate}")


# ------------------------------------------------------------------ 상세 대조

MARKET = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}


def check_detail(conn, rep: Report) -> None:
    for name, fx in fixtures("detail_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            continue
        d = body["data"]
        with conn.cursor() as cur:
            cur.execute("""SELECT c.corp_name, c.stock_code, c.corp_cls, c.industry_code,
                                  i.industry_name, c.ceo_nm, c.established_date
                             FROM company c LEFT JOIN industry i USING (industry_code)
                            WHERE c.corp_code = %s""", (d["corpCode"],))
            row = cur.fetchone()
            cur.execute("""SELECT max(fiscal_year) FROM company_metric
                            WHERE corp_code = %s""", (d["corpCode"],))
            latest = cur.fetchone()[0]
        if row is None:
            rep.check(False, f"{name}: DB 에 없는 기업이 응답됐다")
            continue
        cn, sc, cls, ic, iname, ceo, est = row
        rep.check(d["corpName"] == cn, f"{name}: corpName {d['corpName']} != {cn}")
        rep.check(d["stockCode"] == sc, f"{name}: stockCode {d['stockCode']} != {sc}")
        rep.check(d["industryCode"] == ic, f"{name}: industryCode {d['industryCode']} != {ic}")
        rep.check(d["industryName"] == iname, f"{name}: industryName 불일치")
        rep.check(d["market"] == MARKET.get(cls, "ETC"),
                  f"{name}: market {d['market']} != {MARKET.get(cls, 'ETC')} (corp_cls={cls})")
        rep.check(d.get("ceo") == ceo, f"{name}: ceo {d.get('ceo')} != {ceo}")
        rep.check((d.get("establishedDate") or None) == (est.isoformat() if est else None),
                  f"{name}: establishedDate {d.get('establishedDate')} != {est}")
        rep.check(d.get("dataYear") == latest,
                  f"{name}: dataYear {d.get('dataYear')} != DB 최신연도 {latest}")


# ------------------------------------------------------------------ 검색 대조

def check_search(conn, rep: Report) -> None:
    for name, fx in fixtures("search_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            # 400 은 규격이다. 오류 코드가 있는지만 본다
            rep.check(fx["_status"] == 400 and (body.get("error") or {}).get("code"),
                      f"{name}: 실패 응답에 error.code 가 없다 (status={fx['_status']})")
            continue
        kw = fx["_request"]["params"].get("keyword", "")
        items = body["data"]["items"]
        with conn.cursor() as cur:
            cur.execute("""SELECT count(*) FROM company
                            WHERE corp_name LIKE %s OR stock_code = %s""",
                        (f"%{kw}%", kw))
            total = cur.fetchone()[0]
        rep.check(len(items) <= total,
                  f"{name}: 응답 {len(items)}건 > DB 매칭 {total}건")
        for it in items:
            with conn.cursor() as cur:
                cur.execute("""SELECT corp_name, stock_code, industry_code
                                 FROM company WHERE corp_code = %s""", (it["corpCode"],))
                row = cur.fetchone()
            rep.check(row is not None, f"{name}: DB 에 없는 기업 {it['corpCode']}")
            if row:
                rep.check(it["corpName"] == row[0],
                          f"{name}: corpName {it['corpName']} != {row[0]}")


# ------------------------------------------------------------------ 비교 대조

def check_comparison(conn, rep: Report) -> None:
    for name, fx in fixtures("comparison_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            continue
        d = body["data"]
        ic, year = d["industry"]["code"], d["year"]
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM company WHERE industry_code = %s", (ic,))
            n = cur.fetchone()[0]
        rep.check(d["industry"]["companyCount"] == n,
                  f"{name}: companyCount {d['industry']['companyCount']} != DB {n}")
        rep.check(len(d["companies"]) == n,
                  f"{name}: 응답 기업 {len(d['companies'])} != companyCount {n}")

        with conn.cursor() as cur:
            cur.execute("""SELECT corp_code, metric_code, metric_value
                             FROM company_metric WHERE fiscal_year = %s""", (year,))
            db = {(r[0], r[1]): r[2] for r in cur.fetchall()}
            cur.execute("SELECT metric_code, value_scale FROM metric")
            sc = dict(cur.fetchall())

        for c in d["companies"]:
            for code, got in c["values"].items():
                want = scaled(db.get((c["corpCode"], code)), sc.get(code, 0))
                rep.check(eq(want, got),
                          f"{name} {c['corpCode']} {code}: DB {want} != API {got}")


def main() -> int:
    if not FIX.exists() or not any(FIX.glob("*.json")):
        print(f"응답 원본이 없다: {FIX}")
        print("scripts/probe_backend_api.py 를 먼저 실행하라")
        return 1

    idx = load("_index")
    print(f"대조 대상: {FIX}")
    if idx:
        print(f"수집 시점 base_url: {idx.get('base_url')}")

    total_fail = 0
    with connect() as conn:
        for title, fn in (("[1] 지표 값·자릿수·yoy·비활성 지표 제외", check_metrics),
                          ("[2] 기업 상세 (market·ceo·dataYear 파생 포함)", check_detail),
                          ("[3] 검색", check_search),
                          ("[4] 동종업계 비교", check_comparison)):
            rep = Report()
            print(f"\n{title}")
            fn(conn, rep)
            rep.done(title)
            total_fail += len(rep.fails)

    print(f"\n{'통과' if total_fail == 0 else f'불일치 {total_fail}건'}")
    print("범위: DB ↔ API. 원천 ↔ DB 는 scripts/verify_db.py 가 담당한다")
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
