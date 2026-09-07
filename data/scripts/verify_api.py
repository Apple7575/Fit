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
    ratio()       분자가 없거나 분모가 없거나 0 이하면 null
                  아니면 분자 x 100 / 분모, 소수 1자리 HALF_UP

v2 대응 (S15P21A504-121)
----------------------
기본 응답의 지표 구성은 `is_active` 가 아니라 **`is_core`** 다. V7 이 두 범위를
갈랐다 — core 는 keys 없이 나가는 기본 6종, active 는 keys 로 요청할 수 있는
범위다. rd_ratio 는 active 지만 core 가 아니라서 active 와 맞대면 늘 어긋난다.

`profitability`(operatingMargin·netMargin·debtRatio)도 여기서 대조한다.
백엔드가 카탈로그를 거치지 않고 company_metric 을 직접 읽으므로 같은 방식으로
DB 에서 계산해 맞댄다.

동종업계 비교도 v2 에서 바뀌었다(98). **산업 전체가 아니라 대상 기업 + 고른
peers(최대 3) 만 실린다** — `companyCount` 와 응답 길이가 같다는 v1 의 대조는
성립하지 않는다. 지표도 7종으로 늘었고 그중 `revenue_growth`·`operating_margin`
두 개는 카탈로그에 없이 백엔드가 계산한다. 나머지 5종은 적재된 값이다.
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
RATIO_SCALE = 1                # 백엔드 RATE_SCALE 과 같아야 한다 (수익성 비율)


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


def ratio(numerator, denominator):
    """백엔드 ratio() 와 같은 규칙. 분자가 없거나 분모가 없거나 0 이하면 null.

    분모가 음수일 때 계산하지 않는 것은 증감률과 같은 이유다 — 자본잠식 기업의
    부채비율은 부호가 뒤집혀 '부채가 적은 회사'처럼 보인다.
    """
    if numerator is None or denominator is None or Decimal(denominator) <= 0:
        return None
    q = Decimal(1).scaleb(-RATIO_SCALE)
    return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(
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
        cur.execute("""SELECT metric_code, value_scale, name_ko, unit, is_active, is_core
                         FROM metric""")
        cat = {r[0]: {"scale": r[1], "label": r[2], "unit": r[3],
                      "active": r[4], "core": r[5]}
               for r in cur.fetchall()}

    # v2 에서 두 범위가 갈렸다 (V7). is_core 는 keys 없이 조회했을 때 나가는 기본
    # 목록이고, is_active 는 keys 로 **요청할 수 있는** 범위다. rd_ratio 는
    # active 지만 core 가 아니라서, 기본 응답을 active 와 맞대면 늘 어긋난다
    core = {k for k, v in cat.items() if v["core"]}
    inactive = {k for k, v in cat.items() if not v["active"]}

    for name, fx in fixtures("metrics_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            continue
        data = body["data"]

        # v2 는 profitability 블록을 늘 싣는다(값이 없어도 필드를 생략하지 않는다).
        # 블록이 없으면 응답 원본이 v2 이전이라는 뜻이고, 그 상태로 대조하면
        # 지표 구성부터 전부 어긋나 원인을 못 읽는 실패가 쏟아진다
        if "profitability" not in data:
            rep.check(False, f"{name}: v2 이전 응답이다 (profitability 블록 없음). "
                             "scripts/probe_backend_api.py 로 다시 받아라")
            continue

        corp, year = data["corpCode"], data["year"]
        keys = [m["key"] for m in data["metrics"]]

        # 비활성 지표(rd_cost)는 응답에 없어야 한다
        for code in inactive:
            rep.check(code not in keys, f"{name}: 비활성 지표 {code} 가 응답에 있다")
        # 활성 지표는 값이 없어도 자리가 유지되어야 한다
        # keys 를 준 요청은 그 목록이, 안 준 요청은 기본 6종(is_core)이 나와야 한다
        asked = fx["_request"]["params"].get("keys")
        want_keys = ({k.strip() for k in asked.split(",") if k.strip()}
                     if asked else core)
        rep.check(set(keys) == want_keys,
                  f"{name}: 지표 구성이 다르다 {sorted(set(keys) ^ want_keys)}")

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
            # v2 에는 yoy 파라미터가 없다. 전년 값이 있으면 늘 실린다
            yoy = m.get("yoy")
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

        # 수익성·안정성 비율 (V7 이 더한 블록)
        #
        # 백엔드는 카탈로그를 거치지 않고 company_metric 을 직접 읽는다 —
        # 부채총계·자본총계가 is_active=FALSE 인 내부 지표라 다른 조회에는
        # 걸리지 않아야 하기 때문이다. 여기서도 DB 값으로 직접 계산해 맞댄다
        prof = data["profitability"]
        src = {code: db.get((corp, year, code)) for code in
               ("revenue", "operating_profit", "net_income",
                "total_liabilities", "total_equity")}
        for field, want_ratio in (
                ("operatingMargin", ratio(src["operating_profit"], src["revenue"])),
                ("netMargin", ratio(src["net_income"], src["revenue"])),
                ("debtRatio", ratio(src["total_liabilities"], src["total_equity"]))):
            rep.check(field in prof, f"{name}: profitability.{field} 필드가 없다")
            rep.check(eq(want_ratio, prof.get(field)),
                      f"{name} {field}: DB {want_ratio} != API {prof.get(field)}")


# ------------------------------------------------------------------ 상세 대조
#
# v2(S15P21A504-97)에서 stockCode·market 이 빠지고 address·homepageUrl·dataYear 가
# 들어왔다. corp_cls -> market 파생이 사라져 MARKET 매핑도 함께 지웠다.


def check_detail(conn, rep: Report) -> None:
    for name, fx in fixtures("detail_"):
        body = fx.get("body") or {}
        if not body.get("success"):
            continue
        d = body["data"]
        with conn.cursor() as cur:
            cur.execute("""SELECT c.corp_name, c.industry_code,
                                  i.industry_name, c.ceo_nm, c.established_date,
                                  c.address, c.homepage_url
                             FROM company c LEFT JOIN industry i USING (industry_code)
                            WHERE c.corp_code = %s""", (d["corpCode"],))
            row = cur.fetchone()
            cur.execute("""SELECT max(fiscal_year) FROM company_metric
                            WHERE corp_code = %s""", (d["corpCode"],))
            latest = cur.fetchone()[0]
        if row is None:
            rep.check(False, f"{name}: DB 에 없는 기업이 응답됐다")
            continue
        cn, ic, iname, ceo, est, addr, hp = row
        rep.check(d["corpName"] == cn, f"{name}: corpName {d['corpName']} != {cn}")
        rep.check(d["industryCode"] == ic, f"{name}: industryCode {d['industryCode']} != {ic}")
        rep.check(d["industryName"] == iname, f"{name}: industryName 불일치")
        rep.check(d.get("ceo") == ceo, f"{name}: ceo {d.get('ceo')} != {ceo}")

        # v2 에서 빠진 필드. 없어야 정상이고, 되살아나면 명세와 어긋난 것이다
        for gone in ("stockCode", "market"):
            rep.check(gone not in d, f"{name}: v2 에서 제거된 {gone} 가 응답에 있다")

        # v2 에서 더해진 필드. 적재는 S15P21A504-72 몫이라 지금은 양쪽 다 null 이다.
        # 값이 들어오면 이 대조가 그대로 받는다
        rep.check(d.get("address") == addr,
                  f"{name}: address {d.get('address')} != DB {addr}")
        rep.check(d.get("homepageUrl") == hp,
                  f"{name}: homepageUrl {d.get('homepageUrl')} != DB {hp}")
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

def expected_companies(fx: dict) -> list[str]:
    """응답에 실려야 하는 corpCode 를 순서대로 낸다.

    v2 는 산업 전체를 싣지 않는다 — 대상 기업이 맨 앞이고 그 뒤가 요청한 peers 다.
    백엔드 resolvePeers() 와 같은 규칙으로 중복과 대상 기업 자신을 걷어낸다.
    """
    target = fx["_request"]["path"].split("/")[3]
    raw = fx["_request"]["params"].get("peers") or ""
    out, seen = [target], {target}
    for code in (c.strip() for c in raw.split(",")):
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


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

        # companyCount 는 산업 규모를 알려주는 값일 뿐 응답 길이와 무관하다.
        # v1 은 둘이 같았고 여기서 그것을 대조했다 — v2 에서는 성립하지 않는다.
        want_codes = expected_companies(fx)
        got_codes = [c["corpCode"] for c in d["companies"]]
        rep.check(got_codes == want_codes,
                  f"{name}: 응답 기업 {got_codes} != 기대 {want_codes}")
        target = want_codes[0]
        rep.check(all(c["isTarget"] == (c["corpCode"] == target) for c in d["companies"]),
                  f"{name}: isTarget 이 대상 기업 하나에만 서 있지 않다")

        # 증감률은 전년 값이 있어야 계산된다. 두 해를 함께 읽는다.
        with conn.cursor() as cur:
            cur.execute("""SELECT corp_code, metric_code, metric_value, fiscal_year
                             FROM company_metric WHERE fiscal_year IN (%s, %s)""",
                        (year, year - 1))
            rows = cur.fetchall()
            cur.execute("SELECT metric_code, value_scale FROM metric")
            sc = dict(cur.fetchall())
        db = {(r[0], r[1]): r[2] for r in rows if r[3] == year}
        prev = {(r[0], r[1]): r[2] for r in rows if r[3] == year - 1}

        for c in d["companies"]:
            cc = c["corpCode"]
            for code, got in c["values"].items():
                # v2 가 더한 두 지표는 카탈로그에 없다 — 백엔드가 그 자리에서 계산한다.
                # rd_ratio 는 이름만 비슷하고 실제로는 적재된 값이라 아래 else 로 간다.
                if code == "revenue_growth":
                    want = change_rate(db.get((cc, "revenue")), prev.get((cc, "revenue")))
                elif code == "operating_margin":
                    want = ratio(db.get((cc, "operating_profit")), db.get((cc, "revenue")))
                else:
                    want = scaled(db.get((cc, code)), sc.get(code, 0))
                rep.check(eq(want, got),
                          f"{name} {cc} {code}: DB {want} != API {got}")


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
