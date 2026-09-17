"""사업보고서 원문 → 연구개발비.

초기 R&D 검증 파서의 규칙을 옮겼다. R&D 는 전용 API 가 없다. 8.3MB XML
안의 표 2,216개 중 하나를 찾아내는 작업이고, 파서를 5번 고쳐서야 통과했다.

교차검증 3경로 — 이게 없으면 **틀린 성공**을 잡을 수 없다.
첫 시도에서 SK하이닉스 R&D 를 673만원으로 읽고도 '성공'으로 보고했었다(실제 6.7조).

    ratio_self      표 안 매출로 계산한 비율      분자·분모가 같은 표 → 단위를 몰라도 정확
    ratio_external  API 매출로 계산한 비율        단위 환산이 맞아야 일치한다
    ratio_reported  회사가 문서에 적어둔 비율

    2개 이상이 ±0.5%p 이내로 일치하면 high.

**단위를 못 찾으면 값을 버린다**(`unit_unknown`). 673만원 사건의 원인이 단위
미상이었다. 단위 표기는 표 앞 문장이 아니라 직전의 1행 1열 표에 있다(50건 중 44건).

WP-10 미해결 2건은 여기서 아직 켜지 않았다 — `amount_row_fallback_re`(시프트업
'합계' 단독 라벨)와 `candidate_table_max_rows`(4,937행 병합 표). 켜면 기존 50건의
동작이 바뀔 수 있어 재현 확인 후 별도로 적용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from ..patterns import Patterns, patterns as default_patterns
from .text import norm, squash, to_num


@dataclass
class RndResult:
    status: str = "no_section"            # ok / no_section / no_row
    verdict: str = "no_section"           # high / medium / low / mismatch / unit_unknown / ...
    table_idx: int | None = None
    section: str | None = None
    unit: str | None = None
    unit_src: str | None = None
    amount_raw: float | None = None       # 단위 환산 전 표의 숫자
    rnd_krw: float | None = None          # 원 단위
    ratio_reported: float | None = None   # 회사가 적어둔 비율
    ratio_self: float | None = None       # 표 안 매출로 계산
    ratio_external: float | None = None   # API 매출로 계산
    ratio_decimals: int | None = None
    revenue_in_table: float | None = None
    consolidated_cols: list[int] | None = None
    evidence: dict = field(default_factory=dict)


# ------------------------------------------------------------------ XML 로딩

def parse_xml_bytes(raw: bytes, name: str = "<bytes>"):
    """사업보고서 XML 바이트 → (root, 인코딩). 선언은 utf-8 인데 실제 인코딩이
    다른 문서가 섞여 있다.

    `recover=True` 로 파손된 마크업도 최대한 읽는다 — 안 그러면 표가 안 닫힌
    문서에서 통째로 실패한다.

    **경로가 아니라 바이트를 받는 것**은 Spark 태스크가 HDFS 에서 읽은 내용을
    그대로 넘기기 위해서다 (S15P21A504-73 0차). 로컬 실행은 load_xml 이 파일을
    읽어 이 함수를 부른다 — 두 경로가 같은 코드를 지나야 결과가 갈리지 않는다.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if text.lstrip().startswith("<?xml"):
            text = text.split("?>", 1)[-1]
        root = etree.fromstring(text.encode("utf-8"), parser)
        if root is not None and len(root):
            return root, enc
    raise RuntimeError(f"디코딩 실패: {name}")


def parse_xml_bytes_strict(raw: bytes, name: str = "<bytes>"):
    """RAG 경로에서 복구하되, 원문이 복구한 루트까지 닫혔는지 확인한다."""
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if text.lstrip().startswith("<?xml"):
            text = text.split("?>", 1)[-1]
        parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
        root = etree.fromstring(text.encode("utf-8"), parser)
        if root is None:
            raise etree.XMLSyntaxError("XML root could not be recovered", 0, 0, 0)
        if not _ends_with_root_closing_tag(text, root):
            raise etree.XMLSyntaxError("XML payload is missing its root closing tag", 0, 0, 0)
        return root, enc
    raise RuntimeError(f"디코딩 실패: {name}")


def _ends_with_root_closing_tag(text: str, root) -> bool:
    """실제 markup의 root 종료 태그만 허용한다.

    `recover=True`는 잘린 comment나 CDATA도 root 아래로 복구한다. 원문을
    lexical하게 훑어 그 내부와 attribute quote의 문자열을 종료 태그로 오인하지 않는다.
    """
    local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
    tag = f"{root.prefix}:{local_name}" if root.prefix else local_name
    if not tag:
        return False

    index = 0
    while index < len(text):
        if text[index] != "<":
            index += 1
            continue
        if text.startswith("<!--", index):
            end = text.find("-->", index + 4)
            if end < 0:
                return False
            index = end + 3
            continue
        if text.startswith("<![CDATA[", index):
            end = text.find("]]>", index + 9)
            if end < 0:
                return False
            index = end + 3
            continue
        if text.startswith("<?", index):
            end = text.find("?>", index + 2)
            if end < 0:
                return False
            index = end + 2
            continue

        root_close_end = _root_closing_tag_end(text, index, tag)
        if root_close_end is not None:
            if not text[root_close_end:].strip():
                return True
            index = root_close_end
            continue

        if text.startswith("<!", index):
            end = _declaration_end(text, index)
        else:
            end = _markup_end(text, index)
        if end is None:
            return False
        if end < 0:
            index = -end
        else:
            index = end
    return False


def _root_closing_tag_end(text: str, index: int, tag: str) -> int | None:
    prefix = f"</{tag}"
    if not text.startswith(prefix, index):
        return None
    index += len(prefix)
    while index < len(text) and text[index].isspace():
        index += 1
    return index + 1 if index < len(text) and text[index] == ">" else None


def _markup_end(text: str, start: int) -> int | None:
    quote = None
    index = start + 1
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "<":
            return -index
        elif char == ">":
            return index + 1
        index += 1
    return None


def _declaration_end(text: str, start: int) -> int | None:
    quote = None
    brackets = 0
    index = start + 2
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if text.startswith("<!--", index):
            end = text.find("-->", index + 4)
            if end < 0:
                return None
            index = end + 3
            continue
        if text.startswith("<?", index):
            end = text.find("?>", index + 2)
            if end < 0:
                return None
            index = end + 2
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "[":
            brackets += 1
        elif char == "]" and brackets:
            brackets -= 1
        elif char == ">" and not brackets:
            return index + 1
        index += 1
    return None


def load_xml(path: Path):
    """사업보고서 XML 파일 → (root, 인코딩). 해석은 parse_xml_bytes 가 한다."""
    path = Path(path)
    return parse_xml_bytes(path.read_bytes(), path.name)


def matrix(table, p: Patterns) -> list[list[str]]:
    """TABLE → 2차원 문자열 격자. ROWSPAN/COLSPAN 을 펼친다.

    병합 셀을 펼치지 않으면 열 번호가 어긋나 연결/별도 열 판별이 무너진다.
    """
    grid: dict[tuple[int, int], str] = {}
    pending: dict[int, tuple[int, str]] = {}
    r = 0
    for tr in table.iter("TR"):
        c = 0
        for col, (_left, val) in list(pending.items()):
            grid[(r, col)] = val
        for cell in tr:
            tag = cell.tag.upper() if isinstance(cell.tag, str) else ""
            if tag not in p.rnd.cell_tags:
                continue
            while (r, c) in grid:
                c += 1
            val = squash("".join(cell.itertext()))
            cs = max(1, int(float(cell.get("COLSPAN") or cell.get("colspan") or 1)))
            rs = max(1, int(float(cell.get("ROWSPAN") or cell.get("rowspan") or 1)))
            for dc in range(cs):
                grid[(r, c + dc)] = val
                if rs > 1:
                    # 남은 행 수는 이 행을 포함해 rs다. 행 끝에서 1 줄어 다음 rs-1개 행을 덮는다.
                    # 예전에는 rs-1을 넣고 같은 행 끝에서 바로 줄여 ROWSPAN=2가 자기 행만 덮었다
                    # (우리금융지주 20260313001235 표 825의 `판매관리비` 행이 한 칸 밀린 원인).
                    pending[c + dc] = (rs, val)
            c += cs
        pending = {k: (n - 1, v) for k, (n, v) in pending.items() if n - 1 > 0}
        r += 1
    if not grid:
        return []
    nr = max(k[0] for k in grid) + 1
    nc = max(k[1] for k in grid) + 1
    return [[grid.get((i, j), "") for j in range(nc)] for i in range(nr)]


def collect_tables(root, p: Patterns | None = None) -> list[dict]:
    """문서의 모든 표를 (순번, 직전 TITLE, 직전 텍스트, 격자)로 모은다.

    직전 TITLE 이 섹션 판별에, 직전 텍스트가 단위 탐색에 쓰인다.
    증거(evidence)로 표 순번을 남기려면 문서 전체 순번이 필요하다.
    """
    p = p or default_patterns()
    out: list[dict] = []
    title, recent, idx = "", [], 0
    for el in root.iter():
        tag = el.tag.upper() if isinstance(el.tag, str) else ""
        if tag == "TITLE":
            title, recent = squash("".join(el.itertext())), []
        elif tag in ("P", "SPAN", "TU"):
            t = squash("".join(el.itertext()))
            if t:
                recent = (recent + [t])[-4:]
        elif tag == "TABLE":
            out.append({"idx": idx, "title": title,
                        "caption": " | ".join(recent[-3:]), "m": matrix(el, p)})
            idx += 1
            recent = []
    return out


# ------------------------------------------------------------------ 표 해석

def _label(m, r, ncol=3, p: Patterns | None = None) -> str:
    """행의 라벨. 앞 3열에서 숫자가 아닌 셀만 모은다."""
    p = p or default_patterns()
    seen = []
    for c in m[r][:ncol]:
        c = squash(c)
        if c and c not in seen and not p.rnd.numeric_cell.match(c):
            seen.append(c)
    return " ".join(seen)


def _values(row, p: Patterns, prefer_cols=None):
    """숫자 전용 셀만 (원문, 값, 열번호)로.

    숫자 전용으로 제한하지 않으면 라벨 안의 계산식 '...÷당기매출액×100]' 에서
    100 을 값으로 읽는다.
    """
    out = []
    for j, cell in enumerate(row):
        s = squash(cell)
        if s and p.rnd.numeric_cell.match(s):
            v = to_num(s)
            if v is not None:
                out.append((s, v, j))
    if prefer_cols:
        out.sort(key=lambda x: (0 if x[2] in prefer_cols else 1, x[2]))
    return out


def consolidated_cols(m, p: Patterns) -> set[int] | None:
    """헤더에서 '연결' 열 번호를 찾는다.

    NAVER  : 과목 | 연결 | 연결 | 별도 | 별도
    연결/별도가 한 표에 섞여 있을 때 열 순서에 의존하면 조용히 별도 값을 집는다.
    한쪽만 있으면 구분할 필요가 없으므로 None.
    """
    rows = m[:p.rnd.header_scan_rows]
    n_cols = max((len(r) for r in rows), default=0)
    cons: set[int] = set()
    sep: set[int] = set()
    for r in rows:
        for j in range(min(len(r), n_cols)):
            cell = squash(r[j])
            if p.rnd.consolidated_header in cell:
                cons.add(j)
            elif p.rnd.separate_header in cell:
                sep.add(j)
    if not cons or not sep:
        return None
    return cons - sep


def _decimals(raw: str | None) -> int | None:
    """'19%' → 0, '18.5%' → 1. 보고 비율의 반올림 오차 크기를 알기 위한 것."""
    if not raw:
        return None
    import re
    m = re.search(r"\d+\.(\d+)", squash(raw))
    return len(m.group(1)) if m else 0


def _unit(tables, i: int, p: Patterns):
    """단위 표기 탐색. 자기 표부터 직전 N개까지 거슬러 올라간다.

    해석 규칙은 `business_report.doc.unit_from_blob` 에 있다. 두 파서가 같은
    문서의 같은 표를 보므로 규칙이 갈리면 안 된다 (S15P21A504-73).
    """
    from ..business_report.doc import unit_from_blob

    lookback = p.rnd.unit_lookback_tables
    for k in range(i, max(-1, i - lookback - 1), -1):
        blob = tables[k]["caption"] + " " + " ".join(
            " ".join(r) for r in tables[k]["m"][:3])
        found = unit_from_blob(blob, p.rnd.units)
        if found:
            name, mult = found
            return name, mult, "자기표" if k == i else f"직전표-{i - k}"
    return None, None, None


def extract(tables, external_revenue: float | None = None,
            p: Patterns | None = None) -> RndResult:
    """연구개발 섹션에서 금액·비율을 뽑고 교차검증한다."""
    p = p or default_patterns()
    cands = [(i, t) for i, t in enumerate(tables)
             if p.rnd.section_title.search(t["title"]) and len(t["m"]) >= 3]
    if not cands:
        return RndResult(status="no_section", verdict="no_section")

    for i, t in cands:
        m = t["m"]
        amount = ratio = rev_in_table = None
        ev: dict = {}
        prefer = consolidated_cols(m, p)

        for r in range(len(m)):
            raw_label = _label(m, r, p=p)
            label = norm(raw_label)
            if not label or p.rnd.exclude_row.search(label):
                continue
            vals = _values(m[r], p, prefer)
            if not vals:
                continue

            if amount is None and p.rnd.amount_row.search(label):
                for s, v, col in vals:
                    if "%" not in s and v > 0:
                        amount = v
                        ev["amount"] = {"row": r, "col": col,
                                        "label": raw_label[:45], "raw": s}
                        break

            if ratio is None and p.rnd.ratio_row.search(label):
                pct = [x for x in vals if "%" in x[0]] or vals
                ratio = pct[0][1]
                ev["ratio"] = {"row": r, "col": pct[0][2],
                               "label": raw_label[:45], "raw": pct[0][0]}

            if rev_in_table is None and any(
                    squash(c) in p.rnd.revenue_row_names for c in m[r][:3]):
                for s, v, col in vals:
                    if "%" not in s and v > 0:
                        rev_in_table = v
                        ev["revenue"] = {"row": r, "col": col, "raw": s}
                        break

        if amount is None and ratio is None:
            continue

        unit_nm, mult, unit_src = _unit(tables, i, p)
        out = RndResult(
            status="ok", table_idx=t["idx"], section=t["title"][:45],
            unit=unit_nm, unit_src=unit_src, amount_raw=amount,
            ratio_reported=ratio, revenue_in_table=rev_in_table, evidence=ev,
            consolidated_cols=sorted(prefer) if prefer else None,
            ratio_decimals=_decimals(ev.get("ratio", {}).get("raw")),
        )
        if amount and rev_in_table:
            out.ratio_self = round(amount / rev_in_table * 100, 2)
        if amount and mult:
            out.rnd_krw = amount * mult
            if external_revenue:
                out.ratio_external = round(out.rnd_krw / external_revenue * 100, 2)

        checks = [x for x in (out.ratio_self, out.ratio_external, out.ratio_reported)
                  if x is not None]
        th = p.thresholds
        if not mult:
            out.verdict = "unit_unknown"          # 단위 미상이면 값을 신뢰하지 않는다
        elif len(checks) >= 2 and max(checks) - min(checks) <= th.rnd_ratio_tolerance_pp:
            out.verdict = "high"
        elif len(checks) >= 2:
            out.verdict = "mismatch"
        elif checks and th.rnd_ratio_min_pct < checks[0] <= th.rnd_ratio_max_pct:
            out.verdict = "medium"
        else:
            out.verdict = "low"
        return out

    return RndResult(status="no_row", verdict="no_row")


def from_document(path: Path, external_revenue: float | None = None,
                  p: Patterns | None = None) -> RndResult:
    """사업보고서 파일 하나 → R&D 결과."""
    p = p or default_patterns()
    root, _enc = load_xml(path)
    return extract(collect_tables(root, p), external_revenue, p)
