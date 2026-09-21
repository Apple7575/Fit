"""사업보고서 → 부문별 매출 (segment_metric.segment_revenue).

DART 정형 API 에는 부문별 매출이 없다. 직원현황(empSttus)이 주는 `fo_bbm` 은
**직원 부문**이라 사업 부문과 다르다 — NAVER·카카오·NHN 은 '전사' 한 덩어리이고
NC 는 '관리사무직/연구개발' 이다. 그래서 원문 표에서 뽑는다.

세 회사의 표가 전부 다르게 생겼다 (실측)
----------------------------------------
    삼성전자  부 문 | 매출유형 | 품 목 | 제56기 | 제55기 | 제54기
    NAVER    구분  | 연결 당기 금액 | 비중 | 전기 금액 | 비중     ('- 서치플랫폼')
    크래프톤  사업부문 | 구분 | 제18기 | 제17기 | 제16기        (게임을 지역별로 쪼갬)

**절대 열 번호를 쓰지 않는다.** 크래프톤 2024 의 '기타' 행은 구분 셀이 없어
`[기타, 17176, 13130, 13971]` 로 한 칸 밀려 온다. 열 번호로 집으면 그 행만 다른
연도 값을 읽고, 합계는 그럴듯해 보여서 아무도 눈치채지 못한다. 대신 **행 안에서
몇 번째 숫자 셀인지**로 센다. 밀림과 무관하게 같은 자리를 집는다.

부문 이름은 **0열**을 쓴다. rnd 의 `_label`(앞 3열의 비숫자 셀을 이어붙임)을 쓰면
삼성전자가 'DX 부문 제ㆍ상품,용역 및기타매출 TV, 모니터…' 가 된다.

교차검증 — 부문 합계 vs DART 매출
--------------------------------
이게 유일한 안전장치다. 열을 잘못 집었거나 합계 행을 부문으로 셌으면 합이 어긋난다.
R&D 파서가 673만원(실제 6.7조)을 '성공'으로 보고했던 것과 같은 종류의 사고를
막는 자리다.

    verified      |합 − DART매출| / DART매출 ≤ 5%
    mismatch      넘는다. 값을 버린다
    no_external   대조할 DART 매출이 없다 (그 해 매출 시드가 없는 기업)
    unit_unknown  단위를 못 찾았다. 값을 버린다

내부거래 제거 행('기 타', '부문간 내부거래 제거 등')도 부문으로 남긴다. 빼면 합이
전사 매출을 넘어 검증이 깨지고, 회사가 그렇게 공시한 것이기도 하다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from ..normalize.text import squash, to_num
from .doc import Document, Table

OK, NO_TABLE, NO_ROW = "ok", "no_table", "no_row"
VERIFIED, MISMATCH, NO_EXTERNAL, UNIT_UNKNOWN = (
    "verified", "mismatch", "no_external", "unit_unknown")


@dataclass
class Segment:
    name: str
    amount_raw: float                 # 단위 환산 전
    krw: float | None = None
    rows: int = 1                     # 몇 개 행을 합쳤나 (크래프톤 게임 = 3)


@dataclass
class SegmentResult:
    status: str = NO_TABLE
    verdict: str = NO_TABLE
    table_idx: int | None = None
    section: str | None = None
    unit: str | None = None
    unit_src: str | None = None
    segments: list[Segment] = field(default_factory=list)
    sum_krw: float | None = None
    external_revenue: float | None = None
    gap_ratio: float | None = None    # |합 − 매출| / 매출
    candidates: int = 0               # 후보 표 개수 (진단용)
    evidence: dict = field(default_factory=dict)


def _numbers(row: list[str], p: Patterns) -> list[float]:
    """행의 숫자 전용 셀만 순서대로.

    숫자 전용으로 제한하지 않으면 '제56기' 같은 헤더 셀에서 56 을 값으로 읽는다.
    rnd 의 numeric_cell 규칙을 그대로 쓴다.
    """
    out = []
    for cell in row:
        s = squash(cell)
        if s and p.rnd.numeric_cell.match(s):
            v = to_num(s)
            if v is not None:
                out.append(v)
    return out


def _labels(row: list[str], p: Patterns) -> list[str]:
    """숫자가 처음 나오기 전까지의 라벨 칸. 표마다 라벨 열 수가 달라 위치로 못 센다."""
    out = []
    for cell in row:
        text = squash(cell)
        if text and p.rnd.numeric_cell.match(text):
            break
        out.append(text)
    return out


def _name(row: list[str], sp) -> str:
    """부문 이름 = 0열. 비어 있으면 다음 비숫자 셀."""
    for cell in row[:3]:
        s = sp.name_strip.sub("", squash(cell))
        if s:
            return s
    return ""


def candidates(doc: Document, p: Patterns) -> list[Table]:
    """부문 매출표 후보. 힌트에 걸리는 표를 앞에 둔다.

    **힌트를 필수 조건으로 쓰지 않는다.** 진짜 판정은 합계 대조가 하고, 힌트는
    어느 표부터 볼지 정하는 용도다. 필수로 두면 NAVER 2024 를 놓친다 — 부문
    매출표(idx=33)의 헤더가 '구분 | 연결 | 당기 | 금액 | 비중' 이라 '부문'·'매출'
    같은 말이 표 어디에도 없다. 그 말을 힌트에 넣으면 이번엔 아무 표나 걸린다.

    행 수 상한은 건다. 마크업이 파손된 문서에서 표가 통째로 병합돼 수천 행짜리
    격자가 생긴다 (크래프톤 2024 에 8,189행 표가 실제로 있다). 부문 매출표가
    아니고, 돌리면 느리기만 하다.
    """
    sp = p.business_report.segment
    cap = p.thresholds.candidate_table_max_rows
    hinted, rest = [], []
    for t in doc.tables:
        if not sp.section_title.search(t.title):
            continue
        if not (3 <= t.rows <= cap):
            continue
        if (sp.table_hint.search(t.caption) or sp.table_hint.search(t.head(3))
                or sp.table_hint.search(t.title)):
            hinted.append(t)
        else:
            rest.append(t)
    return hinted + rest


def _from_table(doc: Document, t: Table, p: Patterns) -> tuple[list[Segment], dict]:
    """표 하나 → 부문 목록. 같은 이름은 합친다(크래프톤: 게임 = 대한민국+아시아+…)."""
    sp = p.business_report.segment
    order: list[str] = []
    got: dict[str, Segment] = {}
    ev_rows = []
    for r, row in enumerate(t.m):
        name = _name(row, sp)
        if not name or len(name) > sp.name_max_len:
            continue
        if sp.exclude_row.search(name):
            continue
        # 부문이 아니라 재무상태표 항목이다. 같은 섹션의 '부문별 자산·부채' 표가
        # 부문 매출표로 뽑히는 것을 막는다 — OCI 2025 는 총자산·유형자산·무형자산·
        # 총부채 네 행의 합(2.07조)이 매출(2.14조)과 3.2% 차이라 합계 대조를
        # 우연히 통과했다. 스칼라 하나만 보는 대조로는 가려낼 수 없는 표다.
        if sp.balance_sheet_row.match(name):
            continue
        # 라벨 셋 어디에든 걸리면 매출 행이 아니다. 0열만 보면 현대차처럼
        # 매출액 행과 영업이익 행이 같은 이름으로 합쳐진다.
        if any(sp.exclude_cell.search(squash(c)) for c in row[:3]):
            continue
        # **소계 행은 안쪽 라벨에 숨는다.** 이름만 보면 `제품 | 승용 | 합계` 의
        # '합계' 를 놓쳐 명세 행과 소계 행을 함께 더한다 — 기아 2022 의 제품 매출이
        # 정확히 두 배가 된 원인이다. 숫자가 시작되기 전의 라벨 칸을 전부 본다.
        if any(sp.subtotal_cell.match(squash(c)) for c in _labels(row, p)):
            continue
        nums = _numbers(row, p)
        if len(nums) <= sp.value_position:
            continue                                  # 헤더 행은 여기서 걸러진다
        v = nums[sp.value_position]
        if name in got:
            got[name].amount_raw += v
            got[name].rows += 1
        else:
            got[name] = Segment(name=name, amount_raw=v)
            order.append(name)
        ev_rows.append({"row": r, "name": name[:30], "raw": v})
    return [got[n] for n in order], {"rows": ev_rows[:20]}


def extract(doc: Document, external_revenue: float | None = None,
            p: Patterns | None = None) -> SegmentResult:
    """부문별 매출을 뽑고 DART 매출과 대조한다.

    후보 표를 앞에서부터 보되 **검증을 통과한 첫 표**를 채택한다. 통과하는 표가
    없으면 부문이 가장 많은 결과를 실패 사유와 함께 돌려준다 — 왜 안 됐는지
    보이지 않으면 패턴을 못 늘린다.
    """
    p = p or default_patterns()
    cands = candidates(doc, p)
    if not cands:
        return SegmentResult(status=NO_TABLE, verdict=NO_TABLE)

    best: SegmentResult | None = None
    for t in cands:
        segs, ev = _from_table(doc, t, p)
        if not segs:
            continue
        # 부문이 하나인 표도 본다. SK하이닉스는 '반도체 부문' 단일 부문이라
        # 2개 이상을 요구하면 5개 연도가 통째로 빠진다. 한 부문짜리가 맞는지는
        # 아래 합계 대조가 가린다 — 부문표가 아니면 매출과 안 맞는다.
        unit_nm, mult, unit_src = doc.unit(t)
        res = SegmentResult(
            status=OK, table_idx=t.idx, section=t.title[:45],
            unit=unit_nm, unit_src=unit_src, segments=segs,
            external_revenue=external_revenue, candidates=len(cands), evidence=ev)

        if not mult:
            res.verdict = UNIT_UNKNOWN
        else:
            for s in segs:
                s.krw = s.amount_raw * mult
            res.sum_krw = sum(s.krw for s in segs)
            if not external_revenue:
                res.verdict = NO_EXTERNAL
            else:
                res.gap_ratio = round(
                    abs(res.sum_krw - external_revenue) / external_revenue, 4)
                res.verdict = (VERIFIED
                               if res.gap_ratio <= p.thresholds.segment_sum_tolerance
                               else MISMATCH)
        if res.verdict == VERIFIED:
            return res
        if best is None or len(segs) > len(best.segments):
            best = res

    return best or SegmentResult(status=NO_ROW, verdict=NO_ROW, candidates=len(cands))
