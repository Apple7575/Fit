"""원본 한 단위에서 직접 확인 가능한 실적 숫자만 평가 후보로 추출한다."""

from __future__ import annotations

import re

from pipeline.normalize.text import squash


_METRIC = re.compile(r"매출액|영업이익|당기순이익")
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*(?:년|연도)")
_SINGLE_UNIT = re.compile(r"^단위\s*[:：]\s*(원|천원|백만원|억원|조원)$")
_VALUE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_PARAGRAPH = re.compile(
    r"(?<!\d)(?P<year>(?:19|20)\d{2})\s*년(?:도)?[^\n.]{0,80}?"
    r"(?P<metric>매출액|영업이익|당기순이익)\s*(?:은|는|이|가)?\s*"
    r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>조원|억원|백만원|천원|원)"
)


def performance_candidate(unit: dict[str, object]) -> dict[str, object] | None:
    quote = squash(str(unit["text"]))
    consolidated = bool(re.search(r"연결\s*(?:재무|기준|회사)|\[연결\]", quote))
    separate = bool(re.search(r"별도\s*(?:재무|기준)|\[별도\]", quote))
    if consolidated and separate:
        return None
    if unit["kind"] == "paragraph":
        if re.search(r"예측|추정|전망|괴리|[1-4]분기|누계", quote):
            return None
        match = _PARAGRAPH.search(quote)
        if not match:
            return None
        sentence_start = quote.rfind(".", 0, match.start()) + 1
        sentence = quote[sentence_start:]
        sentence = sentence.split(".", 1)[0]
        if not re.search(r"당사|연결회사", quote[sentence_start:match.end("metric")]):
            return None
        if re.search(r"전년|전기|대비|증감", sentence):
            return None
        if re.search(r"\d[\d,]*\s*(?:조원|억원|백만원|천원|원)", quote[match.end():match.end() + 20]):
            return None
        year, metric, value, unit_text = (match.group(key) for key in ("year", "metric", "value", "unit"))
    elif unit["kind"] == "table_row":
        declared = _SINGLE_UNIT.fullmatch(squash(str(unit.get("table_unit_text") or "")))
        if not declared:
            return None
        header_rows = str(unit.get("table_header_text") or "").splitlines()
        header_text = " ".join(header_rows)
        if re.search(r"예측|추정|전망|수정\s*[전후]|괴리", header_text):
            return None
        row = str(unit["text"]).splitlines()[-1].split("|")
        cells = [squash(cell) for cell in row]
        if not cells:
            return None
        metric = re.sub(r"^[\sⅠⅡⅢⅣIVX\d.()\[\]-]+|[\s\[\]]+$", "", cells[0])
        if not _METRIC.fullmatch(metric):
            return None
        years = [(_YEAR.search(cell), index) for header in header_rows
                 for index, cell in enumerate(header.split("|")) if _YEAR.search(cell)]
        if not years or len({match.group(1) for match, _ in years}) != len(years):
            return None
        year_match, column = max(years, key=lambda pair: int(pair[0].group(1)))
        if any(cell and cell != metric for cell in cells[1:min(index for _, index in years)]):
            return None
        if column >= len(cells) or not _VALUE.fullmatch(cells[column]):
            return None
        year, value, unit_text = year_match.group(1), cells[column], declared.group(1)
    else:
        return None
    basis = "CONSOLIDATED" if consolidated else "SEPARATE" if separate else "UNSPECIFIED"
    basis_label = "연결 기준 " if consolidated else "별도 기준 " if separate else ""
    return {
        "question": f"{year}년 {basis_label}{metric}은 얼마인가?", "answer": f"{value}{unit_text}",
        "section_index": unit["section_index"], "kind": unit["kind"],
        "source_index": unit["source_index"], "source_quote": quote,
        "fiscal_year": year, "unit": unit_text, "accounting_basis": basis,
    }
