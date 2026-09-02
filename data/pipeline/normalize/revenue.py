"""매출액·영업이익 해석 (3경로 교차검증).

초기 매출 검증 파서의 **규칙만** 옮겼다. 달라진 점:
계정명·정규식·임계값을 `patterns.yaml` 에서 읽고, API 호출 대신 `RawStore` 만 본다.

경로 (각각 독립적으로 실패한다)

    A  주요계정 / 계정명       계정명이 표준화되어 있음. XBRL 태깅이 어긋나면 행이 없음
    B  전체재무제표 / 계정코드   ifrs-full_Revenue 등. 태깅이 어긋나면 못 찾음
    C  전체재무제표 / 계정명     회사 원문 이름. 'Ⅰ.영업수익' 처럼 접두사가 붙는다

실측(10개사x5년): A 46/50, B 46/50, C 47/50, 합집합 50/50, 겹치는 43건 불일치 0건

경로 D (R&D 역산)는 여기 없다. `apply_backcalc()` 로 **나중에** 붙인다 —
R&D 파싱 결과가 있어야 계산되기 때문이다(금액 ÷ 보고비율 = 매출).
채택값으로는 절대 쓰지 않는다(순환 방지). 검증 상대로만 쓴다.

판정
    verified                 API 경로 2개 이상이 같은 값
                             또는 API 경로 1개 + 역산(D)이 허용오차 안
    conflict                 API 경로 2개 이상인데 값이 다름 — 사람이 봐야 한다
    single_source            API 경로 1개뿐, 대조할 상대 없음
    single_source_unmatched  API 경로 1개 + 역산이 허용오차 밖
    not_found                전부 실패
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from ..rawstore import RawMissing, RawStore
from .text import squash, to_num


@dataclass
class RevenueResult:
    corp_code: str
    bsns_year: int
    fs_div: str | None = None
    revenue: float | None = None
    revenue_account_nm: str | None = None
    revenue_source: str | None = None          # A_major_name / B_full_id / C_full_name
    revenue_verdict: str = "not_found"
    revenue_paths: dict[str, float] = field(default_factory=dict)
    revenue_worst_gap_pct: float | None = None    # API 경로 간 최대 오차(%)
    backcalc_gap_pct: float | None = None         # 역산 매출과의 차이(%). 기록용
    operating_profit: float | None = None
    rcept_no: str | None = None
    warnings: list[str] = field(default_factory=list)


def _clean_name(s, p: Patterns) -> str:
    """계정명 정규화: 'Ⅰ.영업수익' → '영업수익'.

    전체재무제표는 회사 원문 계정명을 그대로 준다. 넷마블 2023~25 가 번호
    접두사 때문에 경로 C 에서 탈락했고, 이 정규화로 47/50 → 50/50 이 되었다.
    """
    return p.revenue.prefix_strip.sub("", squash(s)).strip()


def _income_rows(rows: list[dict], fs_div: str, p: Patterns) -> list[dict]:
    """손익계산서 행만 고른다.

    행에 fs_div 가 **없는** 응답(전체재무제표)은 그대로 통과시킨다. 여기서
    거르면 213행이 전부 사라진다 — 실제로 이 버그로 폴백이 죽었다.
    """
    out = []
    for r in rows:
        if squash(r.get("sj_div")) not in p.financial_statement.income_statement_div:
            continue
        row_fs = squash(r.get("fs_div"))
        if row_fs and row_fs != fs_div:
            continue
        out.append(r)
    return out


def _by_name(rows: list[dict], names, p: Patterns, *, exclude=True):
    """계정명 정확일치. names 순서가 우선순위다."""
    for want in names:
        for r in rows:
            nm = _clean_name(r.get("account_nm"), p)
            if nm != want:
                continue
            if exclude and p.revenue.exclude.search(nm):
                continue
            v = to_num(r.get("thstrm_amount"))
            if v is not None:
                return v, nm
    return None, None


def _by_id(rows: list[dict], ids: frozenset[str], p: Patterns):
    for r in rows:
        if squash(r.get("account_id")) in ids:
            v = to_num(r.get("thstrm_amount"))
            if v is not None:
                return v, _clean_name(r.get("account_nm"), p)
    return None, None


def resolve(store: RawStore, corp_code: str, year: int,
            p: Patterns | None = None) -> RevenueResult:
    p = p or default_patterns()
    out = RevenueResult(corp_code=corp_code, bsns_year=year)

    try:
        major = store.single_acnt(corp_code, year)
    except RawMissing as e:
        out.warnings.append(str(e))
        major = []

    if major:
        out.rcept_no = squash(major[0].get("rcept_no")) or None

    # 연결 우선, 없으면 별도. 어느 쪽을 썼는지는 fs_div 에 반드시 남긴다
    for fs in p.financial_statement.fs_div_priority:
        paths: dict[str, float] = {}
        names: dict[str, str | None] = {}

        mi = _income_rows(major, fs, p)
        va, na = _by_name(mi, p.revenue.names, p)
        if va is not None:
            paths["A_major_name"] = va
            names["A_major_name"] = na

        profit, _ = _by_name(mi, p.operating_profit.names, p, exclude=False)

        try:
            full = store.single_acnt_all(corp_code, year, fs)
        except RawMissing:
            full = []
        fi = _income_rows(full, fs, p)

        vb, nb = _by_id(fi, p.revenue.account_ids, p)
        if vb is not None:
            paths["B_full_id"] = vb
            names["B_full_id"] = nb
        vc, nc = _by_name(fi, p.revenue.names, p)
        if vc is not None:
            paths["C_full_name"] = vc
            names["C_full_name"] = nc

        if profit is None:
            profit, _ = _by_name(fi, p.operating_profit.names, p, exclude=False)
        if profit is None:
            profit, _ = _by_id(fi, p.operating_profit.account_ids, p)

        if not out.rcept_no and fi:
            out.rcept_no = squash(fi[0].get("rcept_no")) or None

        if not paths:
            continue

        # 채택 우선순위 A → B → C
        for key in ("A_major_name", "B_full_id", "C_full_name"):
            if key in paths:
                out.revenue = paths[key]
                out.revenue_source = key
                out.revenue_account_nm = names.get(key)
                break

        # A·B·C 는 '같은 값을 다른 방법으로 찾은 것'이라 일치해야 정상 → 엄격하게 본다
        if len(paths) >= 2 and out.revenue:
            worst = max(abs(v - out.revenue) / out.revenue for v in paths.values())
            out.revenue_worst_gap_pct = round(worst * 100, 2)
            if worst <= p.thresholds.revenue_path_tolerance:
                out.revenue_verdict = "verified"
            else:
                out.revenue_verdict = "conflict"
                out.warnings.append(
                    "매출 경로 불일치: " + ", ".join(f"{k}={v:,.0f}" for k, v in paths.items()))
        else:
            # 경로 1개. 역산(D)이 붙을 수 있으므로 여기서 확정하지 않는다
            out.revenue_verdict = "single_source"

        out.fs_div = fs
        out.revenue_paths = paths
        out.operating_profit = profit
        return out

    return out


def sanity(rec: RevenueResult) -> str | None:
    """값 자체가 말이 되는지. 파싱이 성공해도 여기서 걸릴 수 있다."""
    if rec.revenue is None:
        return "매출액 없음"
    if rec.revenue <= 0:
        return f"매출액이 0 이하: {rec.revenue:,.0f}"
    if rec.operating_profit is not None and abs(rec.operating_profit) > rec.revenue:
        return (f"영업이익 절대값({rec.operating_profit:,.0f}) > "
                f"매출액({rec.revenue:,.0f})")
    return None


# ------------------------------------------------------- 경로 D (R&D 역산)

def back_calc_revenue(rnd_krw: float | None, ratio_reported: float | None) -> float | None:
    """R&D 금액 ÷ 회사가 보고한 비율 = 매출 역산. **검증 전용.**

    채택값으로 쓰면 R&D 로 매출을 만들고 그 매출로 다시 R&D 를 검증하는 순환이 된다.
    """
    if not rnd_krw or not ratio_reported or ratio_reported <= 0:
        return None
    return rnd_krw / (ratio_reported / 100)


def backcalc_tolerance(ratio_reported: float | None, ratio_decimals: int | None,
                       p: Patterns) -> float:
    """역산 매출의 허용 상대오차.

    보고비율은 반올림되어 적힌다. '19%'는 18.5~19.5%를 뜻하므로 그것으로 역산한
    매출은 최대 0.5/19 = 2.6% 틀어진다. 자릿수가 늘면 허용오차도 함께 줄어든다.
    """
    th = p.thresholds
    if not ratio_reported or ratio_decimals is None:
        return th.revenue_path_tolerance
    half = 0.5 * (10 ** -ratio_decimals)          # %p 단위 반올림 폭
    return min(th.backcalc_max_tolerance, half / ratio_reported + th.backcalc_extra_margin)


def apply_backcalc(fin: RevenueResult, rnd_krw: float | None,
                   ratio_reported: float | None, ratio_decimals: int | None,
                   p: Patterns | None = None) -> RevenueResult:
    """역산 매출을 검증 상대로 붙인다. fin 을 제자리에서 갱신한다.

    API 경로가 2개 이상이면 판정에는 쓰지 않고 차이만 기록한다 — 회사가 어떤
    분모로 비율을 계산했는지 모르기 때문이다(한미반도체 사례).
    API 경로가 1개뿐일 때만 대조 상대로 쓴다.
    """
    p = p or default_patterns()
    if fin.revenue is None:
        return fin

    back = back_calc_revenue(rnd_krw, ratio_reported)
    if back is None:
        return fin

    fin.revenue_paths["D_rnd_backcalc"] = back
    gap = abs(back - fin.revenue) / fin.revenue
    fin.backcalc_gap_pct = round(gap * 100, 2)

    api_paths = [k for k in fin.revenue_paths if k != "D_rnd_backcalc"]
    if len(api_paths) >= 2:
        return fin              # 판정은 API 경로만으로 이미 났다. 차이는 기록만

    if len(api_paths) == 1:
        tol = backcalc_tolerance(ratio_reported, ratio_decimals, p)
        fin.revenue_verdict = "verified" if gap <= tol else "single_source_unmatched"
        fin.revenue_worst_gap_pct = fin.backcalc_gap_pct
    return fin
