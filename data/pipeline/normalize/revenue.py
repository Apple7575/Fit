"""재무제표 지표 해석 — 매출액·영업이익·당기순이익·부채총계·자본총계.

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
class Pick:
    """계정 하나를 여러 경로로 찾은 결과.

    매출은 R&D 역산(경로 D)이 붙어서 판정이 나중에 확정되지만, 여기 담기는
    지표들은 보조 경로가 없어 찾는 즉시 판정이 끝난다.
    """
    value: float | None = None
    source: str | None = None                  # A_major_name / B_full_id / C_full_name
    verdict: str = "not_found"
    paths: dict[str, float] = field(default_factory=dict)
    worst_gap_pct: float | None = None


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
    net_income: Pick = field(default_factory=lambda: Pick())
    total_liabilities: Pick = field(default_factory=lambda: Pick())
    total_equity: Pick = field(default_factory=lambda: Pick())
    rcept_no: str | None = None
    warnings: list[str] = field(default_factory=list)


def _clean_name(s, p: Patterns) -> str:
    """계정명 정규화: 'Ⅰ.영업수익' → '영업수익'.

    전체재무제표는 회사 원문 계정명을 그대로 준다. 넷마블 2023~25 가 번호
    접두사 때문에 경로 C 에서 탈락했고, 이 정규화로 47/50 → 50/50 이 되었다.
    """
    return p.revenue.prefix_strip.sub("", squash(s)).strip()


def _statement_rows(rows: list[dict], fs_div: str, divs) -> list[dict]:
    """지정한 재무제표 구분(sj_div)의 행만 고른다.

    행에 fs_div 가 **없는** 응답(전체재무제표)은 그대로 통과시킨다. 여기서
    거르면 213행이 전부 사라진다 — 실제로 이 버그로 폴백이 죽었다.
    """
    out = []
    for r in rows:
        if squash(r.get("sj_div")) not in divs:
            continue
        row_fs = squash(r.get("fs_div"))
        if row_fs and row_fs != fs_div:
            continue
        out.append(r)
    return out


def _income_rows(rows: list[dict], fs_div: str, p: Patterns) -> list[dict]:
    """손익계산서 행. 매출·영업이익·당기순이익이 여기서 나온다."""
    return _statement_rows(rows, fs_div, p.financial_statement.income_statement_div)


def _balance_rows(rows: list[dict], fs_div: str, p: Patterns) -> list[dict]:
    """재무상태표 행. 부채총계·자본총계가 여기서 나온다."""
    return _statement_rows(rows, fs_div, p.financial_statement.balance_sheet_div)


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

        # 당기순이익·부채총계·자본총계는 매출과 같은 3경로를 쓰되 역산이 없다.
        # 실측(적재 대상 10개사 x 5년 − 상장 이전 3건 = 47건): 셋 다 A·B 가 전부
        # 존재하고 오차 0.00% 로 일치했다.
        # 부채총계·자본총계는 손익계산서가 아니라 재무상태표에서 찾는다.
        #
        # **이 자리여야 한다.** 위 continue 로 버려지는 재무제표 구분에서 부르면
        # 채택되지 않은 값의 경고가 out.warnings 에 남는다. 경고는 기업-연도 단위라
        # load_metrics 가 그 해의 모든 근거 행에 그대로 복사한다 — 근거를 읽는
        # 사람이 채택된 구분에서 난 문제로 오해한다
        mb = _balance_rows(major, fs, p)
        fb = _balance_rows(full, fs, p)
        out.net_income = _pick(mi, fi, p.net_income, p, "당기순이익", out.warnings)
        out.total_liabilities = _pick(mb, fb, p.total_liabilities, p,
                                      "부채총계", out.warnings)
        out.total_equity = _pick(mb, fb, p.total_equity, p, "자본총계", out.warnings)

        out.fs_div = fs
        out.revenue_paths = paths
        out.operating_profit = profit
        return out

    return out


def _pick(major_rows: list[dict], full_rows: list[dict], spec, p: Patterns,
          label: str, warnings: list[str]) -> Pick:
    """한 계정을 매출과 같은 3경로로 찾아 채택하고 판정까지 낸다.

        A  주요계정 / 계정명
        B  전체재무제표 / 계정코드
        C  전체재무제표 / 계정명

    이름은 **정확일치만** 쓴다(`exclude` 를 끄고 부른다). 비슷한 이름의 다른
    계정이 값까지 다르기 때문이다 — '법인세차감전 순이익', '부채와자본총계'.
    근거는 `config/patterns.yaml` 의 각 지표 주석에 있다.
    """
    out = Pick()
    va, _ = _by_name(major_rows, spec.names, p, exclude=False)
    if va is not None:
        out.paths["A_major_name"] = va
    vb, _ = _by_id(full_rows, spec.account_ids, p)
    if vb is not None:
        out.paths["B_full_id"] = vb
    vc, _ = _by_name(full_rows, spec.names, p, exclude=False)
    if vc is not None:
        out.paths["C_full_name"] = vc

    if not out.paths:
        return out

    for key in ("A_major_name", "B_full_id", "C_full_name"):
        if key in out.paths:
            out.value = out.paths[key]
            out.source = key
            break

    # 매출과 같은 규칙. 같은 값을 다른 방법으로 찾은 것이므로 엄격하게 본다.
    if len(out.paths) < 2:
        out.verdict = "single_source"
    elif out.value == 0:
        # 값이 0 이면 상대오차의 분모가 0 이라 계산이 성립하지 않는다. 경로가 둘
        # 이상인 사실은 그대로이므로 single_source 로 적지 않고 값으로 가른다 —
        # 여기서 판정을 잘못 남기면 나중에 이 숫자를 믿을지 판단하는 근거가 틀어진다.
        if all(v == 0 for v in out.paths.values()):
            out.worst_gap_pct = 0.0
            out.verdict = "verified"
        else:
            out.verdict = "conflict"
            warnings.append(f"{label} 경로 불일치(채택값 0): "
                            + ", ".join(f"{k}={v:,.0f}" for k, v in out.paths.items()))
    else:
        # 손실이면 값이 음수라 분모에 절대값을 쓴다
        worst = max(abs(v - out.value) / abs(out.value) for v in out.paths.values())
        out.worst_gap_pct = round(worst * 100, 2)
        if worst <= p.thresholds.revenue_path_tolerance:
            out.verdict = "verified"
        else:
            out.verdict = "conflict"
            warnings.append(f"{label} 경로 불일치: "
                            + ", ".join(f"{k}={v:,.0f}" for k, v in out.paths.items()))
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
