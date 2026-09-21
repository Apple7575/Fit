"""확정 ERD 7개 테이블의 시드 CSV 를 한 번에 만든다 → `curated/seed/`.

팀장 요청 목록이다. 표는 저장 기준 2장대로 `curated/seed/<table_name>.csv` 에
둔다 — `curated/` 바로 밑은 어느 테이블과도 1:1 이 아닌 보조 산출물 자리다
(`company_financials.csv`).

    industry          config/ksic_division.csv                      77행
    company           config/company_universe.csv + 기업개황     2,703행
    metric            Flyway V2·V4·V5·V7·V13·V17 카탈로그의 사본     15행
    company_metric    staged/opendart/financials.csv + 사업보고서 R&D
    segment_metric    .cache/empSttus_*.json + 사업보고서 부문 매출
    company_activity  .cache/otrCprInvstmntSttus_*.json + 사업보고서 시설투자
    company_text      사업보고서 (표 파싱 + 팀 vLLM 추출)

사업보고서 원천은 `scripts/parse_business_reports.py` 와
`scripts/extract_business_text_llm.py` 가 `staged/business_report/` 에 만든다
(S15P21A504-73). **없으면 그 부분만 비고 나머지는 그대로 나온다** — 이 스크립트는
DART 정형 API 만으로도 돌아야 한다. 다만 그때는 행이 크게 줄어 아래 안전장치가
멈춘다. 일부러 그러는 것이면 `--allow-shrink` 다.

`company` 는 정규 시장 상장사 2,703개사다 (corp_cls Y·K·N). 수집 모집단
(`pipeline/universe.py`)과 같은 경계이고, corp_cls=E 1,227개사를 참조하는 행이
다른 표에 하나도 없다. E 까지 넣으려면 `--include-unlisted`.

**헤더는 손으로 적지 않는다.** 저장 기준 9장이 "Flyway 의 실제 컬럼명과 순서에
일치" 를 요구하므로 마이그레이션에서 읽는다 (`pipeline/news/flyway.py`). 컬럼이
늘면 헤더가 따라 늘고, 사람이 목록을 갱신하는 것을 잊어 사전이 낡는 경로를 없앤다.

그래서 요청받은 헤더와 다른 곳이 셋이다. 전부 스키마가 근거다.

  ① `company` 에 corp_name_eng·stock_code·corp_cls·induty_code·listed_date·
     dart_modify_date 가 **더 붙는다.** 이 CSV 하나로 company 를 채울 수 있어야
     한다 — corp_cls 가 없으면 응답의 market(KOSPI/KOSDAQ/KONEX)이 나오지 않는다.
     listed_date·dart_modify_date 는 **빈 칸이다.** 기업개황 응답에 상장일 필드가
     없고(실측) modify_date 는 corpCode.xml 에 있다. 컬럼은 두고 값을 비운다.
  ② `company_metric` 에 **fs_div 가 남는다.** 요청 헤더에는 없지만 DB 에 있는
     컬럼이고, 연결·별도 중 무엇을 읽었는지 잃으면 되짚을 방법이 없다 (V1 주석).
  ③ `metric` 에 **scope 가 없다.** 확정 ERD 가 "제안" 으로 열어 둔 컬럼인데 V13 이
     만들지 않기로 했다 — 사업부 지표를 is_active=FALSE 로 가르는 쪽을 택했다.
     없는 컬럼을 CSV 에만 넣으면 적재가 깨지므로 빼고, 대신 카탈로그에
     segment_revenue·segment_employee_count 가 그 구분을 들고 있다.
     scope 로 가려면 마이그레이션이 먼저다.

두 long 표 모두 **행이 없는 것이 결측**이다. segment_metric 은 V13 주석이 "부문마다
두 지표 행을 항상 만들고 미공시는 NULL" 로 정했지만, 값이 전부 NULL 인
segment_revenue 95행은 넣지 않기로 했다 (MR !81). 부문 목록의 원천이 이 테이블
하나여야 한다는 규칙의 목적은 부문마다 반드시 있는 segment_employee_count 행이
지킨다. 인원을 안 적은 부문만 값 없이 행이 남는다 — 그 부문을 잃지 않기 위해서다.

**segment_revenue 는 부문 축이 다르다** (S15P21A504-73). 직원현황의 fo_bbm 은 직원
부문이고 사업보고서는 사업 부문이라, NAVER·카카오·NHN('전사')·NC('관리사무직/
연구개발')는 이름이 겹치지 않는다. 억지로 맞추면 없는 대응을 지어내는 것이라
사업보고서 부문을 행으로 더한다 — 한 기업에 두 축이 함께 보인다. 팀장 확인.

    python scripts/build_curated_seed.py               # 7종 전부
    python scripts/build_curated_seed.py --only company segment_metric
    python scripts/build_curated_seed.py --verify-db   # DB 와 대조
    python scripts/build_curated_seed.py --allow-shrink  # 행이 줄어도 쓴다

**직전 시드보다 행이 5% 넘게 줄면 그 표를 쓰지 않고 멈춘다** (`_check_shrink`).
기준은 `manifests/seed/<table>.json` 이고 표 전체·기업 수·갈래별 행수를 함께 본다.
검증 7축은 시드에 들어간 행만 보아 사라진 값을 못 잡는다 — 값이 조용히 없어지는
사고가 세 번 있었다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 콘솔이 cp949 면 '→'·'⚠' 에서 죽는다. 형제 스크립트들과 같은 처리다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from build_metric_seed import FIELDS as CM_FIELDS  # noqa: E402
from build_metric_seed import employee_files  # noqa: E402
from build_metric_seed import build_rows as build_company_metric_rows  # noqa: E402
from build_metric_seed import write_seed as write_company_metric  # noqa: E402
from pipeline.news import flyway  # noqa: E402
from pipeline.news.csvio import write_csv  # noqa: E402
from pipeline.patterns import patterns as default_patterns  # noqa: E402
from pipeline import seed_guard  # noqa: E402
from pipeline.normalize.text import squash, to_num  # noqa: E402
from pipeline.paths import (CONFIG, cache_dir, curated_seed_dir,  # noqa: E402
                            raw_api_dir, staged_dir)
from pipeline.targets import by_corp_code, load_targets  # noqa: E402
from pipeline.universe import LISTED_CLS  # noqa: E402

# 시드 계보. manifests/ 는 Git 추적한다 — 원본이 없어도 무엇으로 만들었는지 남아야 한다.
SEED_MANIFEST_DIR = Path(__file__).resolve().parents[1] / "manifests" / "seed"

RE_CORP_CODE = re.compile(r"^[0-9]{8}$")
RE_STOCK_CODE = re.compile(r"^[0-9]{6}$")
CORP_CLS = frozenset(("Y", "K", "N", "E"))

TABLES = ("industry", "company", "metric", "company_metric",
          "segment_metric", "company_activity", "company_text")

# 사업보고서 파싱 산출물 (scripts/parse_business_reports.py) 과 LLM 추출 산출물
# (scripts/extract_business_text_llm.py). 없으면 그 부분만 비고 나머지는 그대로 나온다.
BR = "business_report"

# DB 가 스스로 채우는 칸. NOT NULL DEFAULT now() 라서 빈 셀(=NULL)로 COPY 하면
# 제약에 걸린다. 적재 시각은 적재한 DB 가 찍어야 하는 값이기도 하다.
DB_MANAGED_COLUMNS = frozenset(("created_at", "updated_at"))


def header(table: str) -> list[str]:
    """Flyway 컬럼 순서 그대로. identity 와 DB 가 채우는 칸만 뺀다 (저장 기준 9장)."""
    t = flyway.load().table(table)
    if t is None:
        raise SystemExit(f"{table} 이 마이그레이션에 없다 — backend/ 가 최신인지 확인하라")
    return [c.name for c in t.ordered()
            if not c.identity and c.name not in DB_MANAGED_COLUMNS]


# Flyway V2 → V4(이름 변경) → V5 → V7 → V13 → V17 을 적용한 뒤의 metric 카탈로그.
# SQL 이 정본이고 이것은 사본이다.
#
# **사본이라 낡는다.** 실제로 한 번 낡았다 — V17 이 rd_cost 를 rd_expense 로 바꾸고
# 지표 셋을 더했는데 이 목록이 그대로여서, 이미 머지된 시드가 없는 코드(rd_cost)를
# 들고 있었다. `--verify-db` 는 DB 가 최신일 때만 잡아서 놓쳤다.
# 그래서 `_codes_from_flyway()` 가 생성할 때마다 마이그레이션과 코드 집합을 대조한다.
METRIC_CATALOG = [
    # metric_code,            name_ko,        unit,     scale, source_type,           order, active, core
    ("revenue",                "매출액",         "KRW",    0, "FINANCIAL_STATEMENT",  1, True,  True),
    ("operating_profit",       "영업이익",       "KRW",    0, "FINANCIAL_STATEMENT",  2, True,  True),
    ("net_income",             "당기순이익",     "KRW",    0, "FINANCIAL_STATEMENT",  3, True,  True),
    ("employee_count",         "직원 수",        "PERSON", 0, "EMPLOYEE_STATUS",      4, True,  True),
    ("average_salary",         "1인 평균 급여",  "KRW",    0, "EMPLOYEE_STATUS",      5, True,  True),
    ("average_tenure",         "평균 근속",      "YEAR",   1, "EMPLOYEE_STATUS",      6, True,  True),
    ("rd_ratio",               "R&D/매출",       "%",      1, "DERIVED",              7, True,  False),
    # V17 이 rd_cost 를 이 이름으로 옮겼다. INSERT…SELECT 로 속성을 그대로 복사했으므로
    # 값은 rd_cost 와 같다 (V5 가 만들고 V7 이 display_order 를 8 로 바꾼 것).
    ("rd_expense",             "R&D 비용",       "KRW",    0, "FINANCIAL_STATEMENT",  8, False, False),
    ("total_liabilities",      "부채총계",       "KRW",    0, "FINANCIAL_STATEMENT", 20, False, False),
    ("total_equity",           "자본총계",       "KRW",    0, "FINANCIAL_STATEMENT", 21, False, False),
    ("total_assets",           "자산총계",       "KRW",    0, "FINANCIAL_STATEMENT", 22, False, False),
    ("regular_employee_count", "정규직 수",      "PERSON", 0, "EMPLOYEE_STATUS",     23, False, False),
    ("contract_employee_count", "계약직 수",     "PERSON", 0, "EMPLOYEE_STATUS",     24, False, False),
    ("segment_revenue",        "사업부 매출",    "KRW",    0, "FINANCIAL_STATEMENT", 30, False, False),
    ("segment_employee_count", "사업부 직원 수", "PERSON", 0, "EMPLOYEE_STATUS",     31, False, False),
]

# 직원현황에서 부문마다 만드는 행. segment_revenue 는 원천(사업보고서)과 부문 축이
# 달라 같은 루프에서 만들지 않고 뒤에서 따로 더한다 (S15P21A504-73).
SEGMENT_METRIC = "segment_employee_count"


def _staged_br(name: str) -> list[dict]:
    """staged/business_report/<name> 를 읽는다. 없으면 빈 목록.

    사업보고서 파싱을 안 돌린 환경에서도 나머지 시드는 그대로 나와야 한다 —
    이 스크립트는 DART 정형 API 만으로도 나머지 표를 만들 수 있어야 한다.
    """
    path = staged_dir(BR) / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _rows(path: Path) -> list[dict]:
    """설정 CSV 읽기. 함정 셋은 scripts/load_company.py 주석과 같다.

      - BOM 이 붙어 있다                                    → utf-8-sig
      - 헤더가 ' division_name'(앞 공백)이고 값도 패딩됐다   → strip
      - 쉼표 뒤 공백 때문에 따옴표가 필드 시작으로 인식되지 않아
        업종명이 조각난다                                    → skipinitialspace
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        out = []
        for r in csv.DictReader(f, skipinitialspace=True):
            if None in r:                     # 헤더보다 필드가 많다 = 인용 파손
                raise ValueError(
                    f"{path.name}: 헤더보다 필드가 많은 행이 있다 — 인용 부호를 확인하라. {r}")
            out.append({(k or "").strip(): (v or "").strip() for k, v in r.items()})
        return out


def _write(table: str, rows: list[dict], source: str, notes: list[str],
           stats: dict | None = None) -> Path:
    """행에 헤더 밖의 칸이 있으면 멈춘다 — 스키마가 바뀌었는데 값이 조용히
    버려지는 것을 막는다. 반대로 없는 칸은 빈 셀(=NULL)로 채운다.

    쓰기는 `pipeline/news/csvio.py` 에 맡긴다. BOM 없는 UTF-8 · LF 규칙이
    거기 한 곳에 있다 (저장 기준 6장) — 여기서 다시 정하면 갈라진다.
    """
    fields = header(table)
    extra = {k for r in rows for k in r} - set(fields)
    if extra:
        raise SystemExit(f"{table}: 헤더에 없는 칸 {sorted(extra)} — 스키마를 확인하라")
    rows, dropped = _drop_too_long(table, rows, fields)
    if dropped:
        stats = dict(stats or {})
        stats.update({f"길이 초과로 제외: {k}": v for k, v in dropped.items()})
        print(f"  ⚠ {table}: 길이 초과로 제외 {dict(dropped)}")
    _check_shrink(table, rows, fields)
    dest = curated_seed_dir() / f"{table}.csv"
    write_csv(dest, fields, rows)
    _manifest(table, rows, fields, source, notes, stats)
    return dest


def _drop_too_long(table: str, rows: list[dict],
                   fields: list[str]) -> tuple[list[dict], Counter]:
    """VARCHAR 길이를 넘는 행을 뺀다. **자르지 않는다** (저장 기준 9장).

    잘라서 통과시키면 DB 에는 들어가지만 값이 조용히 달라진다. 빼고 세는 쪽이
    나중에 왜 그 회사가 없는지 되짚을 수 있다.
    """
    limits = {}
    for c in flyway.load().table(table).ordered():
        m = re.fullmatch(r"VARCHAR\((\d+)\)", c.data_type or "")
        if m and c.name in fields:
            limits[c.name] = int(m.group(1))

    kept, dropped = [], Counter()
    for r in rows:
        over = [k for k, n in limits.items() if len(str(r.get(k, "") or "")) > n]
        if over:
            for k in over:
                dropped[k] += 1
            continue
        kept.append(r)
    return kept, dropped


def _manifest(table: str, rows: list[dict], fields: list[str], source: str,
              notes: list[str], stats: dict | None) -> None:
    """시드 계보 — 저장 기준 10장. 원본이 사라져도 무엇으로 만든 표인지 남는다."""
    schema = flyway.load()
    body = {
        "table": table,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "scripts/build_curated_seed.py",
        "header": fields,
        "columns_excluded": sorted(
            {c.name for c in schema.table(table).ordered()} - set(fields)),
        "flyway_files": schema.applied_files,
        "source": source,
        "seed_rows": len(rows),
        # 빈 셀은 NULL 이다. 어느 칸이 얼마나 비었는지가 이 표의 커버리지다.
        "null_counts": {k: sum(1 for r in rows if not str(r.get(k, "")).strip())
                        for k in fields},
        "notes": notes,
    }
    breakdown = seed_guard.breakdown(table, rows)
    if breakdown:
        # 다음 생성 때 이 표를 갈래별로 대조하는 기준이 된다 (_check_shrink).
        body["row_breakdown"] = breakdown
    if rows and "corp_code" in fields:
        body["distinct_corp_codes"] = len({r["corp_code"] for r in rows})
    if rows and "fiscal_year" in fields:
        years = sorted({int(r["fiscal_year"]) for r in rows})
        body["fiscal_years"] = [years[0], years[-1]]
    if stats:
        body["build_stats"] = {k: v for k, v in sorted(stats.items())}

    dest = SEED_MANIFEST_DIR
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{table}.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------- 직전 시드와 행수 대조

# 판단은 pipeline/seed_guard.py 에 있다 — 뉴스 시드도 같은 것을 쓴다.
# main() 이 옵션을 여기에 담는다. _write() 가 표마다 부르는 자리라 인자로
# 들고 다니지 않는다.
_GUARD = {"max_drop": seed_guard.MAX_DROP, "allow_shrink": False}


def _check_shrink(table: str, rows: list[dict], fields: list[str]) -> None:
    seed_guard.check(table, rows, manifest_dir=SEED_MANIFEST_DIR, fields=fields,
                     max_drop=_GUARD["max_drop"], allow_shrink=_GUARD["allow_shrink"])


def _profile_files() -> dict[str, Path]:
    """기업개황 원본. 전 종목은 raw/, 기존 10개사 경로는 .cache/ 에 있다.

    같은 corp_code 가 양쪽에 있으면 raw/ 를 쓴다 — 전 종목 수집이 최신이다.
    """
    out: dict[str, Path] = {}
    for d in (cache_dir(), raw_api_dir()):
        for p in d.glob("company_*.json"):
            out[p.stem.split("_", 1)[1]] = p
    return out


# ------------------------------------------------------------------ industry

def build_industry() -> list[dict]:
    """KSIC 대분류 → industry. company.industry_code 의 FK 대상이다."""
    out, seen = [], set()
    for r in _rows(CONFIG / "ksic_division.csv"):
        code, name = r.get("ksic_division", ""), r.get("division_name", "")
        if not code or not name or code in seen:
            continue
        seen.add(code)
        out.append({"industry_code": code, "industry_name": name})
    return sorted(out, key=lambda r: r["industry_code"])


# ------------------------------------------------------------------- company

def build_company(industry_codes: set[str], *,
                  include_unlisted: bool = False) -> tuple[list[dict], Counter]:
    """유니버스 + 기업개황 → company. 제약 위반 행은 넣지 않고 사유별로 센다.

    **기본은 정규 시장 상장사 2,703개사다** (corp_cls Y·K·N). corp_cls=E 1,227개사는
    사업보고서 제출 의무와 공시 범위가 달라 다른 표들이 아무도 참조하지 않는다 —
    실측으로 company_metric · segment_metric · company_activity 셋 다 E 를 가리키는
    행이 0건이다. 수집 모집단(`pipeline/universe.py`)과도 같아진다.

    판정 규칙은 scripts/load_company.py 와 같게 맞췄다. 적재 직전에 걸릴 행을
    시드 단계에서 미리 뺀다 — CSV 는 통과했는데 DB 가 거부하는 상태를 만들지 않는다.
    """
    stats: Counter = Counter()
    profiles = _profile_files()
    # 결정 C — 종목명이 정본이되 타깃은 사람이 확인한 표시명으로 덮는다.
    # 엔씨소프트의 종목명이 'NC' 라 그대로 두면 사용자가 아는 이름으로 못 찾는다.
    targets = by_corp_code(load_targets())
    out: list[dict] = []

    for r in _rows(CONFIG / "company_universe.csv"):
        corp_code = r.get("corp_code", "")
        stock_code = r.get("stock_code", "")
        corp_cls = r.get("corp_cls", "")
        ksic = r.get("ksic_division", "")

        if not include_unlisted and corp_cls not in LISTED_CLS:
            stats[f"제외: 정규 시장 아님(corp_cls {corp_cls or '(없음)'})"] += 1
            continue

        why = None
        if not RE_CORP_CODE.match(corp_code):
            why = "corp_code 8자리 아님"
        elif stock_code and not RE_STOCK_CODE.match(stock_code):
            why = "stock_code 6자리 숫자 아님"
        elif corp_cls and corp_cls not in CORP_CLS:
            why = "corp_cls 가 Y/K/N/E 밖"
        elif ksic and ksic not in industry_codes:
            why = "industry_code 가 industry 에 없음(FK)"
        if why:
            stats[f"제외: {why}"] += 1
            continue

        target = targets.get(corp_code)
        row = {
            "corp_code": corp_code,
            "corp_name": (target.display_name if target else r.get("corp_name", "")),
            "ceo_nm": "", "established_date": "", "address": "", "homepage_url": "",
            "corp_name_eng": "",
            "industry_code": ksic,
            "stock_code": stock_code,
            "corp_cls": corp_cls,
            "induty_code": r.get("induty_code", ""),
        }

        p = profiles.get(corp_code)
        if p is None:
            stats["개황 없음"] += 1
        else:
            body = json.loads(p.read_text(encoding="utf-8"))
            if str(body.get("status")) != "000":
                stats[f"개황 status {body.get('status')}"] += 1
            else:
                row.update(_profile_fields(body, stats))
                stats["개황 채움"] += 1

        stats[f"corp_cls {corp_cls or '(없음)'}"] += 1
        out.append(row)

    return sorted(out, key=lambda r: r["corp_code"]), stats


def _profile_fields(body: dict, stats: Counter) -> dict:
    """기업개황 응답 → company 의 나머지 칸.

    est_dt 는 YYYYMMDD 다. 형식이 어긋나면 날짜를 지어내지 않고 비운다.
    hm_url 은 'www.samsung.com/sec' 처럼 스킴이 없다 — **손대지 않는다.**
    https 를 붙이는 것은 우리가 만든 값이고, 실제로 http 만 되는 곳이 있다.
    """
    est = squash(body.get("est_dt"))
    if est and not re.fullmatch(r"\d{8}", est):
        stats["est_dt 형식 이상"] += 1
        est = ""
    return {
        "ceo_nm": squash(body.get("ceo_nm")),
        "established_date": f"{est[:4]}-{est[4:6]}-{est[6:]}" if est else "",
        "address": squash(body.get("adres")),
        "homepage_url": squash(body.get("hm_url")),
        "corp_name_eng": squash(body.get("corp_name_eng")),
    }


# -------------------------------------------------------------------- metric

# metric 카탈로그를 건드리는 문장. 값 전체를 해석하지는 않고 **코드 집합만** 본다 —
# 이름·순서까지 SQL 에서 읽으려면 INSERT…SELECT 와 UPDATE 를 해석해야 해서 사실상
# SQL 인터프리터가 된다. 코드가 늘거나 줄거나 바뀌는 것만 잡아도 이번 같은 드리프트는
# 막힌다. 값 불일치는 --verify-db 몫이다.
_METRIC_INSERT_VALUES = re.compile(
    r"INSERT\s+INTO\s+metric\s*\([^)]*\)\s*VALUES(.*)", re.IGNORECASE | re.DOTALL)
_METRIC_INSERT_SELECT = re.compile(
    r"INSERT\s+INTO\s+metric\s*\([^)]*\)\s*SELECT\s+'([\w]+)'", re.IGNORECASE | re.DOTALL)
_METRIC_DELETE = re.compile(
    r"DELETE\s+FROM\s+metric\s+WHERE\s+metric_code\s*(?:=\s*'([\w]+)'"
    r"|IN\s*\(([^)]*)\))", re.IGNORECASE | re.DOTALL)
_QUOTED = re.compile(r"'([^']*)'")


def _codes_from_flyway(migration_dir: Path | None = None) -> set[str]:
    """마이그레이션이 실제로 남긴 metric_code 집합.

    V4 와 V17 처럼 `INSERT … SELECT` 로 새 코드를 만들고 옛 코드를 `DELETE` 하는
    개명이 있어서, 넣은 것과 뺀 것을 순서대로 반영해야 지금 값이 나온다.

    문장 자르기와 주석 지우기는 `pipeline/news/flyway.py` 의 것을 쓴다. 직접
    `split(";")` 하면 **주석 속 코드를 세고, 주석 속 DELETE 가 실재 코드를 지우고,
    문자열 안의 세미콜론에서 문장이 쪼개진다.** 우리 마이그레이션은 주석이 길고
    되돌리기 DDL 을 적는 습관도 있어 실제로 걸린다 (MR !86 리뷰).

    `migration_dir` 은 테스트가 고정 입력을 주기 위한 것이다.
    """
    codes: set[str] = set()
    directory = migration_dir or flyway.MIGRATION_DIR
    for path in sorted(directory.glob("V*.sql"),
                       key=lambda p: int(re.match(r"V(\d+)", p.name).group(1))):
        sql = flyway._strip_comments(path.read_text(encoding="utf-8"))
        for statement in flyway._split_statements(sql):
            values = _METRIC_INSERT_VALUES.search(statement)
            if values:
                # ('revenue', '매출액', …), ('operating_profit', …) → 각 튜플의 첫 값
                for tuple_body in re.findall(r"\(([^)]*)\)", values.group(1), re.DOTALL):
                    first = _QUOTED.search(tuple_body)
                    if first:
                        codes.add(first.group(1))
                continue
            renamed = _METRIC_INSERT_SELECT.search(statement)
            if renamed:
                codes.add(renamed.group(1))
                continue
            # V4 는 CASE 로 두 코드를 한꺼번에 만든다 — SELECT 뒤가 리터럴이 아니다.
            if re.search(r"INSERT\s+INTO\s+metric\b", statement, re.IGNORECASE) \
                    and re.search(r"\bCASE\b", statement, re.IGNORECASE):
                body = statement[re.search(r"\bCASE\b", statement, re.IGNORECASE).end():]
                body = body[:re.search(r"\bEND\b", body, re.IGNORECASE).start()]
                codes.update(m.group(1) for m in re.finditer(r"THEN\s+'([\w]+)'", body))
                continue
            removed = _METRIC_DELETE.search(statement)
            if removed:
                if removed.group(1):
                    codes.discard(removed.group(1))
                else:
                    codes -= set(_QUOTED.findall(removed.group(2)))
    return codes


def check_metric_catalog() -> None:
    """카탈로그 사본이 마이그레이션과 같은지 본다. 어긋나면 아무것도 쓰지 않는다.

    **main 이 첫 파일을 쓰기 전에 부른다.** build_metric 안에서 터지면 industry ·
    company 가 이미 쓰인 뒤라 "시드를 만들지 않고 멈춘다" 가 사실이 아니게 된다
    (MR !86 리뷰).
    """
    catalog = {row[0] for row in METRIC_CATALOG}
    migrations = _codes_from_flyway()
    if catalog != migrations:
        raise SystemExit(
            "metric 카탈로그가 마이그레이션과 어긋난다 — METRIC_CATALOG 를 고쳐야 한다.\n"
            f"  마이그레이션에만: {sorted(migrations - catalog) or '없음'}\n"
            f"  카탈로그에만:     {sorted(catalog - migrations) or '없음'}\n"
            "아무 시드도 만들지 않았다.")


def build_metric() -> list[dict]:
    """지표 카탈로그. 요청 헤더의 scope 는 DB 에 없어 넣지 않는다 (③).

    사업부 지표를 가르는 것은 metric_code 접두사와 is_active=FALSE 다.
    """
    check_metric_catalog()
    return [{
        "metric_code": code, "name_ko": name, "unit": unit, "value_scale": scale,
        "source_type": source, "display_order": order,
        "is_active": str(active).lower(), "is_core": str(core).lower(),
    } for code, name, unit, scale, source, order, active, core in METRIC_CATALOG]


# ------------------------------------------------------------ segment_metric

def build_segment_metric(corp_codes: set[str]) -> tuple[list[dict], Counter]:
    """직원현황(empSttus) → 사업부별 지표.

    부문 축은 fo_bbm 이고 행은 부문 × 성별로 온다. 성별을 더해 부문 하나로 접는다.
    합계 행('성별합계' 등)은 빼야 한다 — 더하면 인원이 두 배가 된다
    (`pipeline/normalize/employee.py` 와 같은 판정을 쓴다).

    **segment_revenue 는 행을 만들지 않는다.** 사업부문별 매출의 원천은 사업보고서
    원문이고 아직 추출 결과가 없다. V13 주석은 "부문마다 두 지표 행을 항상 만들고
    미공시는 NULL" 로 정했지만, 그 규칙의 목적인 "부문 목록의 원천이 이 테이블
    하나" 는 segment_employee_count 행만으로도 지켜진다 — 부문마다 그 행이 반드시
    있기 때문이다. 값이 전부 NULL 인 95행을 넣지 않기로 팀장과 정했다 (MR !81).
    결과적으로 결측 표현이 company_metric 과 같아진다: 행이 없으면 미공시다.
    """
    p = default_patterns()
    f = p.employee.fields
    nulls = p.employee.null_tokens
    stats: Counter = Counter()

    # (corp_code, year, segment) -> 인원 합
    head: dict[tuple, float] = defaultdict(float)
    seen: set[tuple] = set()

    # 전 종목은 raw/, 기존 13개사 경로는 .cache/ 에 있다. 한쪽만 글롭하면
    # collect_employees.py 를 다 돌려도 이 표만 13개사에서 안 늘어난다 —
    # 오류가 나지 않아 아무도 모른다. 목록은 build_metric_seed 와 공유한다.
    for (corp_code, year), path in sorted(employee_files().items()):
        if corp_code not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        for r in body.get("list") or []:
            seg = squash(r.get(f["segment"]))
            if not seg:
                stats["부문명 없음"] += 1
                continue
            if p.employee.total_row.match(seg):
                stats["합계 행 제외"] += 1
                continue
            key = (corp_code, year, seg)
            seen.add(key)
            sm = to_num(r.get(f["total"]), nulls)
            if sm is None:
                # 인원을 안 적은 부문이다. 부문은 남기고 값만 비운다.
                stats["인원 미기재"] += 1
                continue
            head[key] += sm

    out: list[dict] = []
    for corp_code, year, seg in sorted(seen):
        value = head.get((corp_code, year, seg))
        out.append({
            "corp_code": corp_code, "fiscal_year": year, "segment_name": seg,
            "metric_code": SEGMENT_METRIC,
            # 부문은 있는데 인원을 안 적은 경우다. 부문을 잃지 않도록 행은 둔다.
            "metric_value": "" if value is None else f"{value:.4f}",
        })
    stats["직원현황 부문(기업×연도×부문)"] = len(seen)

    # ── 사업보고서 부문별 매출 (S15P21A504-73)
    #
    # 부문 축이 직원현황과 다르다. 직원현황의 fo_bbm 은 **직원 부문**이라
    # NAVER·카카오·NHN 이 '전사' 한 덩어리이고 NC 는 '관리사무직/연구개발' 이다.
    # 사업보고서는 사업 부문(서치플랫폼·커머스·핀테크…)이라 이름이 겹치지 않는다.
    #
    # 그래서 **사업보고서 부문을 행으로 새로 더한다.** 한 기업에 직원 부문과 매출
    # 부문이 함께 보이게 되지만, 이름을 억지로 맞추면 없는 대응을 지어내는 것이다.
    # 팀장 확인을 받은 방향이다.
    #
    # 이름이 겹치는 기업(삼성전자 DX/DS, LG전자 H&A/HE/VS/BS)은 자연스럽게 같은
    # segment_name 아래 두 지표가 붙는다 — V13 이 의도한 모양이다.
    #
    # 값 없는 행은 만들지 않는다. 이 시드는 "행이 없으면 미공시" 규칙을 쓴다
    # (MR !81 에서 빈 segment_revenue 95행을 뺀 것과 같은 판단).
    pk = {(r["corp_code"], r["fiscal_year"], r["segment_name"], r["metric_code"])
          for r in out}
    for r in _staged_br("segment_revenue.csv"):
        corp, year = r["corp_code"], int(r["fiscal_year"])
        if corp not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            continue
        if not r["metric_value"]:
            continue
        key = (corp, year, r["segment_name"], "segment_revenue")
        if key in pk:
            stats["부문 매출 중복(건너뜀)"] += 1
            continue
        pk.add(key)
        out.append({"corp_code": corp, "fiscal_year": year,
                    "segment_name": r["segment_name"],
                    "metric_code": "segment_revenue",
                    "metric_value": r["metric_value"]})
        stats["사업보고서 부문 매출"] += 1

    out.sort(key=lambda r: (r["corp_code"], r["fiscal_year"],
                            r["segment_name"], r["metric_code"]))
    return out, stats


# ---------------------------------------------------------- company_activity

def build_company_activity(corp_codes: set[str]) -> tuple[list[dict], Counter]:
    """타법인 출자현황 → corporate_invest, 사업보고서 → facility.

    activity_type 은 corporate_invest·facility 둘이다. 나머지 둘(ma·transfer)은
    주요사항보고서가 원천인데 **2026-09-21 에 수집하지 않기로 했다** — 수집기를 새로
    뚫는 며칠치 작업이고 화면은 지금 둘로 돌아간다.

    amount 는 **기말 장부가액**(trmend_blce_acntbk_amount)이다. 원천이 사건이
    아니라 사업연도 말 잔액 스냅샷이라서 fiscal_year 축을 쓴다 (V13 4장).
    field_name 은 **원천에 대응하는 값이 없어 비운다** — 투자 분야는 설비투자
    공시의 항목이다. 없는 값을 만들지 않는다.
    """
    stats: Counter = Counter()
    out: list[dict] = []

    for path in sorted(cache_dir().glob("otrCprInvstmntSttus_*.json")):
        parts = path.stem.split("_")
        corp_code, year = parts[1], int(parts[2])
        if corp_code not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        for r in body.get("list") or []:
            name = squash(r.get("inv_prm"))
            if name in ("합계", "계", "소계", "총계"):
                # 표의 마지막 줄이다. 넣으면 출자 건수가 회사마다 하나씩 늘어난다.
                stats["합계 행 제외"] += 1
                continue
            amount = to_num(r.get("trmend_blce_acntbk_amount"))
            if amount is None:
                stats["기말 장부가액 없음(NULL 로 둠)"] += 1
            purpose = squash(r.get("invstmnt_purps"))
            out.append({
                "corp_code": corp_code,
                "activity_type": "corporate_invest",
                "counterparty": name if name not in ("-", "") else "",
                "field_name": "",
                "amount": "" if amount is None else f"{amount:.4f}",
                "purpose": "" if purpose == "-" else purpose,
                "fiscal_year": year,
                "rcept_no": squash(r.get("rcept_no")),
            })
            stats["행"] += 1

    # ── 시설투자 (S15P21A504-73)
    #
    # 사업보고서 '3. 원재료 및 생산설비' 의 투자 계획·실적 표에서 왔다.
    # counterparty 는 **비운다** — 설비투자는 상대방이 있는 거래가 아니다.
    # investment_period 는 표에 있어도 뽑지 않는다 (팀장 기준 2항).
    #
    # amount 가 없는 행은 파싱 단계가 이미 버렸다. 여기 오는 것은 전부 금액이 있다.
    for r in _staged_br("facility.csv"):
        corp_code = r["corp_code"]
        if corp_code not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            continue
        out.append({
            "corp_code": corp_code,
            "activity_type": "facility",
            "counterparty": "",
            "field_name": r["field_name"],
            "amount": r["amount"],
            "purpose": r["purpose"],
            "fiscal_year": int(r["fiscal_year"]),
            "rcept_no": r["rcept_no"],
        })
        stats["시설투자 행"] += 1

    # 대리 키 PK 라 정렬만으로 순서를 고정한다.
    out.sort(key=lambda r: (r["corp_code"], r["fiscal_year"], r["activity_type"],
                            r["counterparty"], r["field_name"], r["rcept_no"]))
    return out, stats


# -------------------------------------------------------------- company_text

def build_company_text(corp_codes: set[str]) -> tuple[list[dict], Counter]:
    """사업보고서 → 기업·연도별 글과 목록. attr_key 6종 (V13).

    원천이 둘이고 성격이 다르다.

        main_product                      표에서 규칙 파싱  → generated_at 비움
        main_business·business_keyword    LLM 추출          → generated_at 채움
        new_business·strategy_change
        rd_field

    generated_at 을 가르는 근거는 V13 주석이다 — "사업보고서에서 그대로 옮긴
    항목은 NULL". 모델·프롬프트가 바뀌면 같은 기업·연도의 결과가 달라지므로
    AI 생성물만 만든 시각을 남긴다.

    (corp_code, fiscal_year, attr_key, seq) 가 UNIQUE 다. 겹치면 적재가 아니라
    여기서 걸려야 한다 — LLM 을 --redo 없이 두 번 돌리면 파일에 같은 키가 두 번
    들어갈 수 있다. 나중 행을 남긴다(재실행이 갱신이 되도록).
    """
    stats: Counter = Counter()
    box: dict[tuple, dict] = {}

    def put(corp, year, attr, seq, value, generated_at):
        if corp not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            return
        value = squash(value)
        if not value:
            stats["빈 값(건너뜀)"] += 1
            return
        key = (corp, year, attr, seq)
        if key in box:
            stats["같은 키 덮어씀"] += 1
        box[key] = {"corp_code": corp, "fiscal_year": year, "attr_key": attr,
                    "seq": seq, "value_text": value, "generated_at": generated_at}
        stats[attr] += 1

    for r in _staged_br("main_product.csv"):
        put(r["corp_code"], int(r["fiscal_year"]), "main_product",
            int(r["seq"]), r["value_text"], "")

    for r in _staged_br("text_llm.csv"):
        put(r["corp_code"], int(r["fiscal_year"]), r["attr_key"],
            int(r["seq"]), r["value_text"], r["generated_at"])

    out = [box[k] for k in sorted(box)]
    stats["행"] = len(out)
    return out, stats


# ----------------------------------------------------------------- 대조(DB)

def verify_db(built: dict[str, list[dict]]) -> int:
    """만든 시드를 DB 현재 상태와 대조한다. 지금 채울 수 있는 것은 metric 뿐이다."""
    from pipeline.db import connect

    bad = 0
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT metric_code, name_ko, unit, value_scale, source_type, "
                    "display_order, is_active, is_core FROM metric")
        db = {r[0]: r[1:] for r in cur.fetchall()}
    seed = {r["metric_code"]: (r["name_ko"], r["unit"], int(r["value_scale"]),
                               r["source_type"], int(r["display_order"]),
                               r["is_active"] == "true", r["is_core"] == "true")
            for r in built.get("metric", [])}
    absent = []
    for code in sorted(set(db) | set(seed)):
        if code not in db:
            absent.append(code); print(f"    DB 에 없음   {code}"); bad += 1
        elif code not in seed:
            print(f"    시드에 없음  {code}"); bad += 1
        elif db[code] != seed[code]:
            print(f"    다름 {code}: DB {db[code]} vs 시드 {seed[code]}"); bad += 1
    print(f"\n[대조] metric  DB {len(db)} · 시드 {len(seed)} · 어긋남 {bad}")
    if absent:
        # 카탈로그가 틀린 것이 아니라 이 DB 가 뒤처진 경우가 흔하다. 어느 쪽인지
        # 사람이 판단할 수 있게 마지막으로 적용된 마이그레이션을 함께 보여준다.
        with connect() as c, c.cursor() as cur:
            cur.execute("SELECT version, description FROM flyway_schema_history "
                        "WHERE success ORDER BY installed_rank DESC LIMIT 1")
            last = cur.fetchone()
        print(f"       이 DB 의 마지막 마이그레이션 V{last[0]} ({last[1]}) — "
              f"카탈로그를 늘린 마이그레이션이 아직 적용되지 않았을 수 있다")
    return 1 if bad else 0


# ----------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", choices=TABLES,
                    help="이 표만 다시 만든다 (기본: 7종 전부)")
    ap.add_argument("--verify-db", action="store_true",
                    help="metric 카탈로그를 DB 와 대조한다")
    ap.add_argument("--include-unlisted", action="store_true",
                    help="company 에 corp_cls=E(기타) 1,227개사까지 넣는다")
    seed_guard.add_arguments(ap)
    args = ap.parse_args()
    _GUARD.update(max_drop=args.max_drop, allow_shrink=args.allow_shrink)
    want = set(args.only or TABLES)
    built: dict[str, list[dict]] = {}

    # 파일을 하나라도 쓰기 전에 본다. --only 로 metric 을 빼도 마찬가지다 —
    # 카탈로그가 낡았다는 사실은 어느 표를 만들든 알아야 한다.
    check_metric_catalog()

    # industry 와 company 는 뒤 표들의 FK 대상이라 --only 와 무관하게 먼저 읽는다.
    industry = build_industry()
    industry_codes = {r["industry_code"] for r in industry}
    company, company_stats = build_company(
        industry_codes, include_unlisted=args.include_unlisted)
    corp_codes = {r["corp_code"] for r in company}

    if "industry" in want:
        built["industry"] = industry
        dest = _write("industry", industry, "config/ksic_division.csv",
                      ["V3 가 같은 77건을 SQL 로 시드한다 — CSV 적재는 중복이다"])
        print(f"industry          {len(industry):>7,}행  → {dest.name}")

    if "company" in want:
        built["company"] = company
        filled = company_stats["개황 채움"]
        dest = _write("company", company,
                      "config/company_universe.csv + 기업개황(company.json)",
                      ["정규 시장 상장사만 (corp_cls Y·K·N). E 1,227개사는 다른 표가"
                       " 아무도 참조하지 않는다 — --include-unlisted 로 넣을 수 있다",
                       "listed_date 는 기업개황 응답에 필드가 없다 (실측)",
                       "dart_modify_date 는 corpCode.xml 에 있고 이 경로로는 안 온다",
                       "address 는 공백만 정규화했다 — 원문과 그 외 차이 없음",
                       "타깃 10개사의 corp_name 은 targets.csv 의 display_name 으로 덮는다"],
                      company_stats)
        print(f"company           {len(company):>7,}행  → {dest.name}")
        print(f"  개황 채움 {filled:,}/{len(company):,} ({filled / len(company):.1%}) · "
              + " · ".join(f"{k} {v:,}" for k, v in sorted(company_stats.items())
                           if k.startswith(("제외", "개황 status", "est_dt"))))
        print("  " + " · ".join(f"{k} {v:,}" for k, v in sorted(company_stats.items())
                                if k.startswith("corp_cls")))

    if "metric" in want:
        metric = build_metric()
        built["metric"] = metric
        dest = _write("metric", metric,
                      "Flyway V2·V4·V5·V7·V13·V17 의 INSERT (SQL 이 정본, 이것은 사본)",
                      ["요청 헤더의 scope 는 DB 에 없어 뺐다 — 넣으려면 마이그레이션이 먼저다",
                       "생성할 때마다 마이그레이션의 코드 집합과 대조한다 —"
                       " 어긋나면 시드를 만들지 않는다",
                       "값(이름·순서·플래그)까지 보려면 --verify-db 다"])
        print(f"metric            {len(metric):>7,}행  → {dest.name}")
        print("  요청 헤더의 scope 는 DB 에 없어 빠졌다 — 넣으려면 마이그레이션이 먼저다")

    if "company_metric" in want:
        # 이 표만 build_metric_seed.py 가 쓴다. 그쪽 헤더는 상수라 스키마와
        # 벌어질 수 있으므로 여기서 한 번 맞춰 본다.
        if CM_FIELDS != header("company_metric"):
            raise SystemExit(f"build_metric_seed.FIELDS 가 Flyway 와 다르다: "
                             f"{CM_FIELDS} != {header('company_metric')}")
        rows, st = build_company_metric_rows()
        built["company_metric"] = rows
        _check_shrink("company_metric", rows, CM_FIELDS)
        dest = write_company_metric(rows)
        _manifest("company_metric", rows, CM_FIELDS,
                  "staged/opendart/financials.csv (fnlttMultiAcnt 2021~2025)",
                  ["연결 우선·별도 폴백. 고른 쪽을 fs_div 에 남긴다",
                   "결측은 행을 넣지 않는다 — metric_value 가 NOT NULL 이다",
                   "KRW 가 아닌 통화는 넣지 않는다 (환산은 추정이다)"],
                  {k: (dict(v) if isinstance(v, Counter) else v)
                   for k, v in st.items()})
        print(f"company_metric    {len(rows):>7,}행  → {dest.name}")
        print(f"  회사 {len({r['corp_code'] for r in rows}):,} · "
              f"연결 {st['used_fs']['CFS']:,} · 별도 {st['used_fs']['OFS']:,} · "
              f"통화로 제외 {dict(st['skipped_currency'])}")
        outside = {r["corp_code"] for r in rows} - corp_codes
        if outside:
            print(f"  ⚠ company 에 없는 corp_code {len(outside):,}개 — FK 위반이다")

    if "segment_metric" in want:
        rows, st = build_segment_metric(corp_codes)
        built["segment_metric"] = rows
        dest = _write("segment_metric", rows,
                      ".cache/empSttus_*.json (직원 현황) + "
                      "staged/business_report/segment_revenue.csv (사업보고서)",
                      ["segment_employee_count 의 부문 축은 fo_bbm 이고 성별 행을"
                       " 접어 하나로 만든다",
                       "segment_revenue 는 사업보고서 원문에서 오고 부문 축이 다르다"
                       " — 직원 부문과 사업 부문이 한 기업에 함께 보인다 (S15P21A504-73)",
                       "값 없는 행은 만들지 않는다 (MR !81 과 같은 규칙)"], st)
        print(f"segment_metric    {len(rows):>7,}행  → {dest.name}")
        print(f"  회사 {len({r['corp_code'] for r in rows}):,} · "
              + " · ".join(f"{k} {v:,}" for k, v in sorted(st.items())))

    if "company_activity" in want:
        rows, st = build_company_activity(corp_codes)
        built["company_activity"] = rows
        dest = _write("company_activity", rows,
                      ".cache/otrCprInvstmntSttus_*.json (타법인 출자현황) + "
                      "staged/business_report/facility.csv (사업보고서 시설투자)",
                      ["activity_type 은 corporate_invest·facility 둘 — ma·transfer 는"
                       " 수집하지 않기로 했다 (2026-09-21 팀장 확정)",
                       "amount 는 기말 장부가액이다 (사건이 아니라 연말 잔액 스냅샷)",
                       "corporate_invest 의 field_name 은 원천에 대응하는 값이 없어 비운다",
                       "facility 의 counterparty 는 비운다 — 상대방이 있는 거래가 아니다",
                       "investment_period 는 표에 있어도 뽑지 않는다 (팀장 기준 2항)"], st)
        print(f"company_activity  {len(rows):>7,}행  → {dest.name}")
        print(f"  회사 {len({r['corp_code'] for r in rows}):,} · "
              + " · ".join(f"{k} {v:,}" for k, v in sorted(st.items())))
        print("  activity_type 은 corporate_invest·facility 둘이다 —"
              " ma·transfer 는 수집하지 않기로 했다 (2026-09-21)")

    if "company_text" in want:
        rows, st = build_company_text(corp_codes)
        built["company_text"] = rows
        dest = _write("company_text", rows,
                      "staged/business_report/main_product.csv (표 파싱) + "
                      "staged/business_report/text_llm.csv (LLM 추출)",
                      ["main_product 는 '주요 제품' 열을 그대로 옮긴 것이라"
                       " generated_at 이 비어 있다 (V13 주석)",
                       "나머지 5종은 팀 vLLM(Qwen3-32B-AWQ) 추출물이라 generated_at 을"
                       " 남긴다 — 모델·프롬프트가 바뀌면 결과가 달라진다",
                       "seq 는 사업보고서 기재 순서다. 글 항목은 늘 0 이다",
                       "근거가 없으면 행을 만들지 않는다 (팀장 기준 4항)"], st)
        print(f"company_text      {len(rows):>7,}행  → {dest.name}")
        print(f"  회사 {len({r['corp_code'] for r in rows}):,} · "
              + " · ".join(f"{k} {v:,}" for k, v in sorted(st.items())))

    print(f"\n→ {curated_seed_dir()}")
    return verify_db(built) if args.verify_db else 0


if __name__ == "__main__":
    sys.exit(main())
