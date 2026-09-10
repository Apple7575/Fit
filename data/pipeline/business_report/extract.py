"""사업보고서 한 건 → 네 산출물. **파일도 네트워크도 건드리지 않는다.**

`scripts/parse_business_reports.py`(로컬 단일 프로세스)와 Spark 잡이 **같은 함수**를
부른다. 0차 실험의 전제가 "인프라를 바꿔도 결과가 같다" 인데, 두 경로가 각자
파싱하면 그 전제를 확인할 수 없다 (S15P21A504-73).

    parse_one(raw_bytes, corp_code=..., fiscal_year=..., rcept_no=...) -> DocumentResult

순수 함수로 둔 이유
------------------
Spark 태스크 안에서 부르려면 이것들이 없어야 한다.

    파일 쓰기      워커마다 파일이 생겨 한 CSV 에 동시 쓰기가 깨진다
    전역 상태      태스크가 어느 노드에서 돌지 모른다
    경로 의존      HDFS 에서 읽은 바이트를 그대로 받아야 한다

그래서 이 모듈은 dict 목록만 돌려주고, 그것을 CSV 로 쓸지 Parquet 로 쓸지 Kafka 로
보낼지는 부르는 쪽이 정한다.

컬럼 이름은 시드 CSV 와 같게 맞춘다
---------------------------------
`staged/business_report/*.csv` 의 헤더를 그대로 쓴다. 0차 대조가 열 이름까지 같아야
성립하고, 이름을 바꾸면 `build_curated_seed.py` 도 같이 고쳐야 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..normalize import rnd as rnd_mod
from ..patterns import Patterns, patterns as default_patterns
from . import facility as fac_mod
from . import segments as seg_mod
from . import texts as txt_mod
from .doc import Document

# staged/business_report/*.csv 의 헤더. 부르는 쪽이 이 순서로 쓴다.
SEGMENT_FIELDS = ["corp_code", "fiscal_year", "segment_name", "metric_value",
                  "rcept_no", "verdict", "unit", "table_idx", "gap_ratio", "sum_krw"]
FACILITY_FIELDS = ["corp_code", "fiscal_year", "field_name", "purpose", "amount",
                   "rcept_no", "verdict", "unit", "table_idx"]
PRODUCT_FIELDS = ["corp_code", "fiscal_year", "seq", "value_text", "rcept_no",
                  "table_idx"]
RND_FIELDS = ["corp_code", "fiscal_year", "rd_expense", "rd_ratio", "rcept_no",
              "verdict", "raw_verdict", "unit"]
SUMMARY_FIELDS = ["corp_code", "corp_name", "fiscal_year", "rcept_no", "bytes",
                  "tables", "seg_verdict", "seg_count", "fac_verdict", "fac_count",
                  "product_count", "rnd_verdict", "business_chars", "rd_chars",
                  "seconds", "error"]

# R&D 는 단위 미상이면 값을 버린다 (rnd.py 673만원 사건).
RND_DROP_VERDICTS = ("unit_unknown",)


@dataclass
class DocumentResult:
    """문서 하나의 산출물. 전부 dict 목록이라 그대로 직렬화된다."""
    corp_code: str
    fiscal_year: int
    rcept_no: str
    segments: list[dict] = field(default_factory=list)
    facilities: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    rnd: dict | None = None
    passages: dict | None = None          # {corp_code, fiscal_year, rcept_no, business, rd}
    summary: dict = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return bool(self.summary.get("error"))


def parse_one(source, *, corp_code: str, fiscal_year: int, rcept_no: str,
              corp_name: str = "", external_revenue: float | None = None,
              size_bytes: int | None = None,
              p: Patterns | None = None) -> DocumentResult:
    """원문(경로 또는 바이트) → 네 산출물 + 판정.

    **예외를 밖으로 던지지 않는다.** 11,395건을 도는 중에 한 건이 터져서 잡 전체가
    죽으면 안 된다. 실패는 summary.error 로 남고 나머지 산출물은 빈 목록이다.
    Spark 태스크에서도 같은 이유로 이 규칙이 필요하다 — 태스크 실패는 재시도를
    부르고, 파손된 문서는 몇 번 다시 해도 파손이다.
    """
    import time

    p = p or default_patterns()
    res = DocumentResult(corp_code=corp_code, fiscal_year=fiscal_year,
                         rcept_no=rcept_no)
    row = {"corp_code": corp_code, "corp_name": corp_name,
           "fiscal_year": fiscal_year, "rcept_no": rcept_no,
           "bytes": size_bytes if size_bytes is not None else "", "error": ""}
    t0 = time.monotonic()
    try:
        doc = Document(source, p, rcept_no=rcept_no)
        row["tables"] = len(doc.tables)
        if size_bytes is None and doc.path is not None:
            row["bytes"] = doc.path.stat().st_size

        # ── 부문별 매출
        sr = seg_mod.extract(doc, external_revenue, p)
        row["seg_verdict"], row["seg_count"] = sr.verdict, len(sr.segments)
        if sr.verdict == seg_mod.VERIFIED:
            res.segments = [{
                "corp_code": corp_code, "fiscal_year": fiscal_year,
                "segment_name": s.name, "metric_value": f"{s.krw:.4f}",
                "rcept_no": rcept_no, "verdict": sr.verdict, "unit": sr.unit,
                "table_idx": sr.table_idx, "gap_ratio": sr.gap_ratio,
                "sum_krw": f"{sr.sum_krw:.0f}"} for s in sr.segments]

        # ── 시설투자
        fr = fac_mod.extract(doc, p)
        row["fac_verdict"], row["fac_count"] = fr.verdict, len(fr.items)
        if fr.verdict == fac_mod.OK:
            res.facilities = [{
                "corp_code": corp_code, "fiscal_year": fiscal_year,
                "field_name": it.field_name or "", "purpose": it.purpose or "",
                "amount": f"{it.krw:.4f}", "rcept_no": rcept_no,
                "verdict": fr.verdict, "unit": fr.unit,
                "table_idx": fr.table_idx} for it in fr.items]

        # ── 주요 제품 + LLM 입력 구간
        tr = txt_mod.extract(doc, p)
        row["product_count"] = len(tr.main_product)
        res.products = [{
            "corp_code": corp_code, "fiscal_year": fiscal_year, "seq": seq,
            "value_text": v, "rcept_no": rcept_no,
            "table_idx": tr.product_table_idx}
            for seq, v in enumerate(tr.main_product)]
        business = tr.passages.get("business", "")
        rd_text = tr.passages.get("rd", "")
        row["business_chars"], row["rd_chars"] = len(business), len(rd_text)
        if business or rd_text:
            res.passages = {"corp_code": corp_code, "fiscal_year": fiscal_year,
                            "rcept_no": rcept_no, "business": business, "rd": rd_text}

        # ── R&D. 이미 펴 둔 표를 넘겨 문서를 다시 열지 않는다
        tables = [{"idx": t.idx, "title": t.title, "caption": t.caption, "m": t.m}
                  for t in doc.tables]
        rr = rnd_mod.extract(tables, external_revenue, p)
        row["rnd_verdict"] = rr.verdict
        if rr.rnd_krw and rr.verdict not in RND_DROP_VERDICTS:
            res.rnd = {
                "corp_code": corp_code, "fiscal_year": fiscal_year,
                "rd_expense": f"{rr.rnd_krw:.4f}",
                "rd_ratio": rr.ratio_reported or rr.ratio_external or rr.ratio_self or "",
                "rcept_no": rcept_no, "verdict": rr.verdict,
                "raw_verdict": rr.verdict, "unit": rr.unit}
    except Exception as e:                    # noqa: BLE001 — 한 건이 전체를 멈추지 않는다
        row["error"] = f"{type(e).__name__}: {e}"[:200]

    row["seconds"] = round(time.monotonic() - t0, 1)
    res.summary = row
    return res
