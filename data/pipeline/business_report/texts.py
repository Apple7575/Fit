"""사업보고서 → company_text 6종.

    attr_key          어떻게                             왜
    main_product      표에서 규칙 파싱                    '주요 제품' 열이 목록 그대로다
    main_business     LLM                                섹션 본문이 수천 자다
    business_keyword  LLM                                의미 해석
    new_business      LLM                                의미 해석
    strategy_change   LLM                                의미 해석
    rd_field          LLM                                의미 해석

팀장 기준 5항 — "숫자나 표처럼 규칙적으로 추출할 수 있는 값은 파싱을 우선한다.
LLM 은 의미 해석이 필요한 데이터에 사용한다." main_product 는 표에 열로 들어 있어
파싱이 맞고, 나머지는 본문 서술이라 LLM 이다.

이 모듈은 **LLM 을 호출하지 않는다.** 넘길 원문 구간을 고르는 데까지만 한다.
호출은 `llm.py` 가 하고, 그래야 이 모듈을 네트워크 없이 시험할 수 있다.

컨텍스트 상한 때문에 구간을 고른다
--------------------------------
팀 vLLM 서버가 12,288 토큰(입력+출력)이다. 사업보고서 한 건이 8MB 라 통째로는
못 넣는다. 그래서 attr_key 가 실제로 나오는 섹션만 잘라 보낸다.

    main_business·business_keyword   1. 사업의 개요 / 회사의 개요
    new_business·strategy_change     사업의 개요 + 기타 참고사항
    rd_field                         6. 주요계약 및 연구개발활동
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..patterns import Patterns, patterns as default_patterns
from ..normalize.text import squash
from .doc import Document

# 목록 셀을 항목으로 쪼갠다. '등' 으로 끝나는 꼬리는 항목이 아니다.
_SPLIT = re.compile(r"[,·ㆍ/]|\s및\s")
_TAIL = re.compile(r"\s*등\s*$")

# 제품 목록 열 헤더. 삼성전자 '주요 제품', NAVER '주요영업', 크래프톤 '품목'
_PRODUCT_HEADER = re.compile(r"주요\s*제품|주요\s*서비스|주요\s*영업|품\s*목|제품\s*및\s*서비스")


@dataclass
class TextResult:
    main_product: list[str] = field(default_factory=list)
    product_table_idx: int | None = None
    passages: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _items(cell: str, tp) -> list[str]:
    """셀 하나 → 항목 목록. 'TV, 모니터, 냉장고 등' → [TV, 모니터, 냉장고]"""
    out = []
    for part in _SPLIT.split(squash(cell)):
        s = _TAIL.sub("", squash(part))
        if not s or len(s) > 60 or tp.null_tokens.match(s):
            continue
        if s.isdigit():
            continue
        # 제품이 아닌 값. 행 라벨만 걸러서는 안 잡힌다 — 삼성전자는 첫 칸이 '기타'
        # 이고 제품 칸에 '부문간 내부거래 제거 등' 이 들어 있다.
        if tp.product_exclude.search(s):
            continue
        out.append(s)
    return out


def main_products(doc: Document, p: Patterns) -> tuple[list[str], int | None]:
    """'주요 제품' 열을 그대로 목록으로 만든다.

    부문별 매출표와 같은 표에 들어 있는 경우가 많다 (삼성전자 idx=39 는
    부 문 | 주요 제품 | 매출액 | 비중). 그래서 부문 파서와 같은 섹션을 본다.

    기재 순서를 보존한다 — company_text.seq 가 "사업보고서 기재 순서" 라고
    V13 주석에 적혀 있다. 중복은 첫 등장 자리를 남기고 지운다.
    """
    tp = p.business_report.text
    sp = p.business_report.segment
    cap = p.thresholds.candidate_table_max_rows
    for t in doc.tables:
        if not (sp.section_title.search(t.title) or tp.main_product_section.search(t.title)):
            continue
        if not (2 <= t.rows <= cap):
            continue
        col = None
        for r in t.m[:3]:
            for c, cell in enumerate(r):
                if _PRODUCT_HEADER.search(squash(cell)):
                    col = c
                    break
            if col is not None:
                break
        if col is None:
            continue
        seen: list[str] = []
        for row in t.m[1:]:
            if col >= len(row):
                continue
            name = squash(row[0]) if row else ""
            if name and sp.exclude_row.search(name):
                continue
            for it in _items(row[col], tp):
                if it not in seen:
                    seen.append(it)
        if seen:
            return seen, t.idx
    return [], None


def passages(doc: Document, p: Patterns) -> dict[str, str]:
    """LLM 에 넘길 원문 구간. 섹션 본문을 이어 붙이고 상한에서 자른다.

    같은 제목의 섹션이 여러 번 나오므로 전부 이어 붙인다 (연결/별도 주석이 같은
    이름을 쓴다). 자를 때는 앞에서부터 남긴다 — 사업보고서는 개요가 앞에 온다.
    """
    tp = p.business_report.text
    limit = tp.llm_input_chars

    def collect(rx, prefer: str | None = None) -> str:
        """prefer 가 제목에 든 섹션을 앞으로 옮긴 뒤 상한에서 자른다.

        '1. 사업의 개요' 와 '1. 회사의 개요' 가 둘 다 걸리는데 문서 순서로는
        회사의 개요(법적 명칭·종속회사 목록)가 먼저 나온다. 그대로 이어 붙이면
        정작 필요한 사업의 개요가 상한 밖으로 밀린다 — 삼성전자·SK하이닉스·
        크래프톤에서 실제로 그랬다.
        """
        head, tail = [], []
        for s in doc.sections_matching(rx):
            t = s.text()
            if not t:
                continue
            block = f"[{s.title}]\n{t}"
            (head if prefer and prefer in s.title else tail).append(block)
        return "\n\n".join(head + tail)[:limit]

    return {
        "business": collect(tp.main_business_section, prefer="사업의 개요"),
        "rd": collect(tp.rd_section),
    }


def extract(doc: Document, p: Patterns | None = None) -> TextResult:
    p = p or default_patterns()
    products, idx = main_products(doc, p)
    res = TextResult(main_product=products, product_table_idx=idx,
                     passages=passages(doc, p))
    for k, v in res.passages.items():
        if not v:
            res.notes.append(f"{k} 구간 없음")
    return res
