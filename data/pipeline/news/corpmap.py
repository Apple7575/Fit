"""검색어(회사명) → corp_code 매핑.

회사명 문자열만으로 기업을 붙이지 않는다. 기존 기업 마스터의 원천인
`config/company_universe.csv`(상장사 3,930건, F-04 적재 입력)를 색인해서 붙이고,
붙지 않으면 corp_code 를 비운 채 사유를 남긴다.

**추정 매칭을 하지 않는다.** 부분일치·유사도로 붙이면 "삼성전자" 검색 결과가
삼성전기에 붙는 식의 오류가 조용히 DB 로 들어간다. 정확일치와 표기 정규화 일치까지만
자동으로 처리하고, 둘 이상 걸리면 실패로 본다 — 사람이 보고 정해야 하는 것이다.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config"

# 표기 정규화에서 떼는 법인 표기. 앞뒤 어디에 붙어도 같은 회사다.
_LEGAL_FORMS = ("주식회사", "(주)", "㈜", "(유)", "유한회사", "(재)", "(사)")


def normalize_name(value: str) -> str:
    """법인 표기·공백·기호를 지우고 소문자로 만든다.

    'SK하이닉스' 와 '에스케이하이닉스(주)' 는 이 함수로도 같아지지 않는다. 한글
    음차 표기까지 맞추려면 사전이 필요하고, 그건 추정이므로 하지 않는다.
    """
    text = value or ""
    for form in _LEGAL_FORMS:
        text = text.replace(form, "")
    return re.sub(r"[\W_]+", "", text).casefold()


@dataclass
class Mapping:
    corp_code: str
    method: str
    reason: str = ""


class CorpMap:
    """회사명 색인. 같은 이름에 기업이 둘 이상이면 그 이름은 자동 매핑에서 뺀다."""

    def __init__(self, rows: list[dict[str, str]]):
        self._exact: dict[str, set[str]] = {}
        self._normalized: dict[str, set[str]] = {}
        self.row_count = len(rows)
        for row in rows:
            code = (row.get("corp_code") or "").strip()
            if not code:
                continue
            for column in ("corp_name", "dart_corp_name"):
                name = (row.get(column) or "").strip()
                if not name:
                    continue
                self._exact.setdefault(name, set()).add(code)
                self._normalized.setdefault(normalize_name(name), set()).add(code)

    def resolve(self, company_name: str) -> Mapping:
        name = (company_name or "").strip()
        if not name:
            return Mapping("", "", "empty_query_company_name")
        hit = self._exact.get(name)
        if hit and len(hit) == 1:
            return Mapping(next(iter(hit)), "exact_name")
        if hit:
            return Mapping("", "", f"ambiguous_name:{len(hit)}_candidates")
        key = normalize_name(name)
        hit = self._normalized.get(key)
        if hit and len(hit) == 1:
            return Mapping(next(iter(hit)), "normalized_name")
        if hit:
            return Mapping("", "", f"ambiguous_normalized_name:{len(hit)}_candidates")
        return Mapping("", "", "not_in_company_universe")


def load(path: Path | None = None) -> CorpMap:
    """company_universe.csv 를 읽어 색인을 만든다. BOM 이 붙어 있어 utf-8-sig 로 읽는다."""
    target = path or (CONFIG / "company_universe.csv")
    with target.open(encoding="utf-8-sig", newline="") as stream:
        return CorpMap(list(csv.DictReader(stream)))
