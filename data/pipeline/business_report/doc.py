"""사업보고서 XML 한 건에 대한 읽기 계층.

`pipeline/normalize/rnd.py` 가 표만 필요해서 만든 `collect_tables` 를 확대한 것이다.
company_text 는 표가 아니라 **문단**에서 나오므로 둘을 같은 순서로 들고 있어야 한다.

rnd.py 와 나눠 둔 이유
---------------------
rnd.py 는 검증까지 끝난 코드다(50건 3경로 교차검증). 거기에 문단 수집을 끼워 넣으면
회귀 기준선(tests/fixtures/normalize)을 다시 만들어야 한다. XML 로딩·격자 변환처럼
검증된 부분은 **가져다 쓰고** 새로 필요한 것만 여기서 더한다.

한 문서가 8MB · 표 2,000개다. 파싱은 문서당 한 번만 하고 결과를 재사용한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..patterns import Patterns, patterns as default_patterns
from ..normalize.rnd import load_xml, matrix, parse_xml_bytes
from ..normalize.text import squash

# 본문 문단으로 볼 태그. rnd.collect_tables 의 캡션 수집과 같은 집합이다.
TEXT_TAGS = ("P", "SPAN", "TU")

# '단위' 표기 바로 뒤 구간만 잘라낸다. 괄호·대괄호가 닫히거나 20자를 넘으면 끊는다.
_UNIT_SCOPE = re.compile(r"단위\s*[)\]]?\s*[::]?\s*([^)\]|]{0,20})")


def unit_from_blob(blob: str, units) -> tuple[str, int] | None:
    """'단위' 표기 **바로 뒤**에서만 단위를 찾는다.

    문자열 전체에서 찾으면 본문 서술에 걸린다. 삼성전자 2024 시설투자표의 캡션이
    "(시설투자 현황) 2024년 ... 53.6조원의 시설투자가 이루어졌습니다" 이고 표의
    단위는 '억원' 인데, 전체 검색은 앞의 '조원' 을 먼저 집어 값이 1만 배가 됐다.

    units 는 긴 표기가 앞이어야 한다 ('십억원' 이 '억원' 보다 먼저).
    """
    for m in _UNIT_SCOPE.finditer(blob):
        scope = m.group(1)
        for name, mult in units:
            if name in scope:
                return name, mult
    return None


@dataclass
class Table:
    idx: int                       # 문서 전체 표 순번. 증거로 남긴다
    title: str                     # 직전 TITLE (= 섹션 제목)
    caption: str                   # 직전 문단 3개
    m: list[list[str]]             # ROWSPAN/COLSPAN 을 펼친 격자

    @property
    def rows(self) -> int:
        return len(self.m)

    def head(self, n: int = 3) -> str:
        return " ".join(" ".join(r) for r in self.m[:n])


@dataclass
class Section:
    """TITLE 하나와 그 아래 본문·표.

    사업보고서의 TITLE 은 계층이 아니라 평면이다. '2. 주요 제품 및 서비스' 다음
    TITLE 이 나올 때까지가 그 섹션이며, 같은 제목이 여러 번 나올 수 있다
    (연결/별도 주석이 같은 이름을 쓴다). 그래서 제목으로 찾을 때는 **전부** 본다.
    """
    title: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)

    def text(self, limit: int | None = None) -> str:
        t = "\n".join(self.paragraphs)
        return t[:limit] if limit else t


class Document:
    """사업보고서 한 건. 생성 시점에 한 번 훑고 그 뒤로는 메모리에서 본다."""

    def __init__(self, source: Path | str | bytes, p: Patterns | None = None,
                 rcept_no: str | None = None):
        """파일 경로 또는 XML 바이트를 받는다.

        바이트를 받는 것은 Spark 태스크가 HDFS 에서 읽은 내용을 임시 파일로
        떨구지 않고 그대로 넘기기 위해서다 (S15P21A504-73 0차). 어느 쪽이든
        parse_xml_bytes 를 지나므로 로컬과 분산의 해석이 갈리지 않는다.
        """
        if isinstance(source, (bytes, bytearray)):
            self.path = None
            self.rcept_no = rcept_no or ""
            root, self.encoding = parse_xml_bytes(bytes(source), rcept_no or "<bytes>")
        else:
            self.path = Path(source)
            self.rcept_no = rcept_no or self.path.stem.replace("document_", "")
            root, self.encoding = load_xml(self.path)
        self.p = p or default_patterns()
        self.sections: list[Section] = []
        self.tables: list[Table] = []
        self._walk(root)

    def _walk(self, root) -> None:
        """문서를 한 번만 훑어 섹션·표를 동시에 만든다.

        표의 caption 은 rnd.collect_tables 와 같은 규칙(직전 문단 3개)을 유지한다.
        R&D 파서가 단위를 그 문자열에서 찾고 있어 규칙이 갈리면 안 된다.
        """
        cur = Section(title="")
        self.sections.append(cur)
        recent: list[str] = []
        idx = 0
        for el in root.iter():
            tag = el.tag.upper() if isinstance(el.tag, str) else ""
            if tag == "TITLE":
                cur = Section(title=squash("".join(el.itertext())))
                self.sections.append(cur)
                recent = []
            elif tag in TEXT_TAGS:
                t = squash("".join(el.itertext()))
                if t:
                    cur.paragraphs.append(t)
                    recent = (recent + [t])[-4:]
            elif tag == "TABLE":
                tb = Table(idx=idx, title=cur.title,
                           caption=" | ".join(recent[-3:]), m=matrix(el, self.p))
                self.tables.append(tb)
                cur.tables.append(tb)
                idx += 1
                recent = []

    # ------------------------------------------------------------------ 조회

    def sections_matching(self, rx) -> list[Section]:
        """제목이 정규식에 걸리는 섹션 전부. 같은 제목이 여러 번 나올 수 있다."""
        return [s for s in self.sections if s.title and rx.search(s.title)]

    def tables_matching(self, rx, *, in_title=None) -> list[Table]:
        """제목·캡션·머리 3행 중 어디든 걸리는 표.

        머리 행까지 보는 이유는 캡션이 비어 있는 표가 흔하기 때문이다 —
        삼성전자 부문별 매출표(idx=65)가 캡션 없이 헤더에 '부 문' 만 있다.
        """
        out = []
        for t in self.tables:
            if in_title is not None and not in_title.search(t.title):
                continue
            if rx.search(t.title) or rx.search(t.caption) or rx.search(t.head()):
                out.append(t)
        return out

    def unit(self, table: Table) -> tuple[str | None, int | None, str | None]:
        """표의 금액 단위 → (표기, 원 환산 배수, 어디서 찾았나).

        단위 표기는 표 앞 문장이 아니라 **직전의 1행 1열 표**에 있다 (rnd.py 실측:
        50건 중 44건). 그래서 자기 표부터 직전 N개까지 거슬러 오른다. 규칙과 배수
        목록을 rnd 쪽 patterns 에서 그대로 가져와 두 파서가 갈리지 않게 한다.
        """
        rp = self.p.rnd
        i = table.idx
        for k in range(i, max(-1, i - rp.unit_lookback_tables - 1), -1):
            t = self.tables[k]
            found = unit_from_blob(t.caption + " " + t.head(3), rp.units)
            if found:
                name, mult = found
                return name, mult, "자기표" if k == i else f"직전표-{i - k}"
        return None, None, None
