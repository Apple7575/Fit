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
from ..universe import is_excluded

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
    """회사명 색인. 같은 이름에 기업이 둘 이상이면 그 이름은 자동 매핑에서 뺀다.

    **`corp_cls='E'`(기타법인)는 색인에 넣지 않는다.** `company` 시드가 정규 시장
    상장사만 담고 있어(E 1,227개사는 참조하는 표가 없어 뺐다) E 로는 FK 가 성립하지
    않는다. 붙을 수 없는 기업 때문에 이름이 "후보 2개"로 갈려 상장사까지 못 붙는
    일이 실제로 있었다 — SK·삼성물산·미래에셋증권이 각각 E 와 Y 로 한 건씩 있어
    뉴스 1,030건이 통째로 버려졌다 (2026-09-15 유니버스 100개사 수집).

    이것은 추정 매칭이 아니다. 붙을 수 없는 후보를 후보에서 빼는 것뿐이다.
    """

    def __init__(self, rows: list[dict[str, str]]):
        self._exact: dict[str, set[str]] = {}
        self._normalized: dict[str, set[str]] = {}
        self.row_count = len(rows)
        self.excluded_rows = 0
        for row in rows:
            code = (row.get("corp_code") or "").strip()
            if not code:
                continue
            if (row.get("corp_cls") or "").strip().upper() == "E":
                self.excluded_rows += 1
                continue
            for column in ("corp_name", "dart_corp_name"):
                name = (row.get(column) or "").strip()
                if not name:
                    continue
                self._exact.setdefault(name, set()).add(code)
                self._normalized.setdefault(normalize_name(name), set()).add(code)

    def add_aliases(self, aliases: dict[str, str]) -> None:
        """사람이 확인한 별칭을 얹는다. 자동 색인보다 **먼저** 본다 — 별칭은
        이름이 아니라 종목코드 같은 근거로 확인한 것이라 더 강하다."""
        self._alias = {name.strip(): code for name, code in aliases.items() if name.strip()}

    def resolve(self, company_name: str) -> Mapping:
        name = (company_name or "").strip()
        if not name:
            return Mapping("", "", "empty_query_company_name")
        code = getattr(self, "_alias", {}).get(name)
        if code:
            return Mapping(code, "alias")
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


ALIAS_PATH = CONFIG / "news_company_aliases.yaml"


def load_aliases(path: Path | None = None) -> dict[str, str]:
    """사람이 확인한 이름 별칭 → corp_code.

    자동 매칭은 여전히 정확일치·표기 정규화까지만 한다. 이 표는 **사람이 종목코드
    같은 이름 밖 근거로 확인한 것만** 예외로 등록하는 자리다. 조건과 근거는
    `config/news_company_aliases.yaml` 머리말에 적혀 있다.
    """
    target = path or ALIAS_PATH
    if not target.exists():
        return {}
    import yaml

    doc = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for entry in doc.get("aliases") or []:
        code = (entry.get("corp_code") or "").strip()
        if not code:
            continue
        for name in entry.get("names") or []:
            if (name or "").strip():
                out[name.strip()] = code
    return out


def load(path: Path | None = None) -> CorpMap:
    """company_universe.csv 를 읽어 색인을 만든다. BOM 이 붙어 있어 utf-8-sig 로 읽는다."""
    target = path or (CONFIG / "company_universe.csv")
    with target.open(encoding="utf-8-sig", newline="") as stream:
        # 스팩은 색인에 넣지 않는다 — 사업이 없어 수집 대상에서 뺐다
        # (`pipeline/universe.py` 주석에 근거가 있다). 수집 드라이버가 검색어에서
        # 빼는 것과 **같은 규칙**이어야 한다. 한쪽만 걸면 기사를 받아 놓고 붙일
        # 기업이 없어 staged 에서 통째로 버려진다.
        rows = [r for r in csv.DictReader(stream)
                if not is_excluded(r.get("corp_name") or "")]
        corp_map = CorpMap(rows)
    corp_map.add_aliases(load_aliases())
    return corp_map
