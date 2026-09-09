"""사업보고서 → 시설투자 (company_activity.activity_type='facility').

company_activity 의 유형 4종 중 corporate_invest 만 원천이 있었다(타법인 출자현황
API). facility 는 정형 API 가 없어 사업보고서 '3. 원재료 및 생산설비' 의
투자 계획·실적 표에서 뽑는다.

열 순서를 믿지 않는다
--------------------
회사마다 열이 다르다 (실측).

    삼성전자   구 분 | 내 용       | 투자기간  | 대상자산 | 투자액
    SK하이닉스 구분  | 투자대상자산 | 투자효과  | 투자 기간 | 기투자액(누적) | 비고

그래서 **헤더 행을 찾아 이름으로 열을 매핑**한다. 위치로 집으면 두 회사 중 하나는
투자기간을 금액으로 읽는다.

투자액 열이 없으면 시설투자표가 아니다
------------------------------------
같은 섹션에 원재료 매입액표·유형자산 변동표(기초/증감/상각/기말)·가동률표가 함께
있다. 금액 열을 넓게 잡으면 그것들이 전부 걸려 들어온다 — 현대차 2024 의 유형자산
변동표가 실제로 그렇게 걸렸다. 투자액 계열 헤더를 필수로 두는 것이 정밀도의 전부다.

investment_period 는 뽑지 않는다 (팀장 기준 2항). 표에 있어도 버린다.

남은 한계 — 셀이 밀린 행은 인접 기간 열을 읽는다
----------------------------------------------
헤더 이름으로 열을 잡으므로, 어떤 행에 셀이 하나 빠져 밀려 오면 그 행만 옆 열을
읽는다. 아시아나항공 2021 표가 그렇다 —

    항공운송 | 아시아나항공 | 항공기, 항공기재 | 316,688 | 393,755 | …
    항공운송 | 일반설비     | 25,728          |  20,390 | …          ← 한 칸 밀림

밀린 행은 '제34기예산' 대신 '제34기실적' 을 읽는다. 둘 다 그 행의 투자 금액이라
자릿수는 맞고 기간 구분만 어긋난다. 부문별 매출은 합계 대조로 이런 밀림을 잡지만
시설투자는 대조할 외부 값이 없어 같은 방법을 못 쓴다.

고치려면 행 안에서 숫자 셀을 세는 방식(segments.value_position)으로 바꿔야 하는데,
그러면 열 이름으로 '향후투자액' 을 피하는 지금 규칙을 못 쓴다. 자릿수가 통째로
틀리는 쪽(향후투자액·달러)이 더 위험해서 이름 매핑을 택했다.

값이 없으면 행을 만들지 않는다 (팀장 기준 4항). 시설투자를 공시하지 않은 기업은
facility 행이 0건인 것이 맞고, 그것이 "투자를 안 했다"는 뜻은 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from ..normalize.text import squash, to_num
from .doc import Document, Table

OK, NO_TABLE, NO_ROW = "ok", "no_table", "no_row"
UNIT_UNKNOWN = "unit_unknown"


@dataclass
class Facility:
    field_name: str | None
    purpose: str | None
    amount_raw: float
    krw: float | None = None


@dataclass
class FacilityResult:
    status: str = NO_TABLE
    verdict: str = NO_TABLE
    table_idx: int | None = None
    section: str | None = None
    unit: str | None = None
    unit_src: str | None = None
    items: list[Facility] = field(default_factory=list)
    candidates: int = 0
    evidence: dict = field(default_factory=dict)


def _header_row(m: list[list[str]], fp) -> tuple[int, dict[str, int]] | None:
    """헤더 행과 열 매핑. 투자액 열이 없으면 헤더로 인정하지 않는다.

    앞쪽 몇 행만 본다 — 표 중간에 소제목 행이 또 나오는 경우가 있는데 그걸
    헤더로 잡으면 데이터 행이 반으로 준다.

    **금액 열은 첫 일치가 아니라 우선순위로 고른다.** LS 2023 표가
    `총소요자금 | 기지출금액 | 향후투자액` 인데 왼쪽부터 훑으면서 '투자액' 을
    찾으면 향후투자액이 걸린다 — 아직 안 쓴 돈을 투자 금액으로 읽는다. 실제로
    '공통 경상투자' 가 2,226백만원 대신 61백만원으로 들어갔다.
    """
    for r, row in enumerate(m[:4]):
        cols: dict[str, int] = {}
        best_rank = len(fp.amount_header_priority)
        for c, cell in enumerate(row):
            s = squash(cell)
            if not s:
                continue
            if not fp.amount_exclude_header.search(s):
                for rank, rx in enumerate(fp.amount_header_priority):
                    if rx.search(s):
                        if rank < best_rank:
                            best_rank, cols["amount"] = rank, c
                        break
            if "purpose" not in cols and fp.purpose_header.search(s):
                cols["purpose"] = c
            elif "field" not in cols and fp.field_header.search(s):
                cols["field"] = c
        if "amount" in cols:
            return r, cols
    return None


def candidates(doc: Document, p: Patterns) -> list[Table]:
    fp = p.business_report.facility
    cap = p.thresholds.candidate_table_max_rows
    out = []
    for t in doc.tables:
        if not fp.section_title.search(t.title):
            continue
        if not (2 <= t.rows <= cap):
            continue
        if _header_row(t.m, fp):
            out.append(t)
    return out


def _cell(row: list[str], cols: dict[str, int], key: str) -> str | None:
    c = cols.get(key)
    if c is None or c >= len(row):
        return None
    return squash(row[c]) or None


def extract(doc: Document, p: Patterns | None = None) -> FacilityResult:
    """시설투자 항목을 뽑는다.

    후보 표 중 **항목이 가장 많은 표**를 고른다. 부문별 매출과 달리 대조할 외부
    값이 없어 '통과한 첫 표' 규칙을 쓸 수 없다. 대신 투자액 헤더를 필수로 두고
    단위를 못 찾으면 통째로 버린다 — 단위 미상이 자릿수를 통째로 틀리게 한다는
    것은 R&D 파서가 이미 겪었다(673만원 사건).
    """
    p = p or default_patterns()
    fp = p.business_report.facility
    cands = candidates(doc, p)
    if not cands:
        return FacilityResult(status=NO_TABLE, verdict=NO_TABLE)

    best: FacilityResult | None = None
    for t in cands:
        hdr = _header_row(t.m, fp)
        if not hdr:
            continue
        hrow, cols = hdr
        items: list[Facility] = []
        for row in t.m[hrow + 1:]:
            name = _cell(row, cols, "field")
            if name and fp.exclude_row.search(name):
                continue
            purpose = _cell(row, cols, "purpose")
            # 목적 자리에 투자기간이 들어왔다 = 열이 밀렸다. 금액도 못 믿으므로 버린다.
            # 한국전력공사가 해마다 한 행씩 이렇게 온다 (실측).
            if purpose and fp.period_in_purpose.search(purpose):
                continue
            raw_amount = _cell(row, cols, "amount") or ""
            # 원화가 아니면 버린다. 환산은 추정이라 하지 않는다 — build_metric_seed 의
            # 통화 규칙과 같다. 효성티앤씨는 해외 종속회사 설비투자를 '$15백만' 으로
            # 적는데, $ 를 떼면 15가 남아 15원짜리 설비투자가 된다.
            if fp.foreign_currency.search(raw_amount):
                continue
            amount = to_num(raw_amount)
            if amount is None or amount <= 0:
                continue
            if purpose and fp.exclude_row.search(purpose):
                purpose = None
            items.append(Facility(field_name=name, purpose=purpose, amount_raw=amount))
        if not items:
            continue

        unit_nm, mult, unit_src = doc.unit(t)
        res = FacilityResult(
            status=OK, table_idx=t.idx, section=t.title[:45], unit=unit_nm,
            unit_src=unit_src, items=items, candidates=len(cands),
            evidence={"header_row": hrow, "cols": cols})
        if not mult:
            res.verdict = UNIT_UNKNOWN
        else:
            for it in items:
                it.krw = it.amount_raw * mult
            res.verdict = OK
        if best is None or len(items) > len(best.items):
            best = res

    return best or FacilityResult(status=NO_ROW, verdict=NO_ROW, candidates=len(cands))
