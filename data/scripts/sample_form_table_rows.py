"""company_table_row 의 사람 검수 표본을 뽑아 번호 목록 Markdown 으로 쓴다 (docs/decisions/0003 성공 기준).

    python data/scripts/sample_form_table_rows.py --corp-code 01021666 ... --per-form 2 --out docs/experiments/form-table-review.md

표본 하나는 "표 하나의 본문 행 하나"다. 정형화된 값(행 이름 경로 · 열 · 값 · 단위 · 소속 법인)과
그 행을 담은 원문 청크의 해당 줄을 나란히 보여 사람이 같은지 대조한다. 접속은 DATABASE_URL 이다.
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import database_url  # noqa: E402

import psycopg  # noqa: E402

ROWS_SQL = """
SELECT corp_code, rcept_no, table_index, form_code, section_title, entity_scope, unit, header,
       row_no, matrix_row, row_labels, column_key, fiscal_year, value_num, value_text, parse_status, evidence_id
FROM company_table_row
WHERE corp_code = ANY(%s)
ORDER BY corp_code, rcept_no, table_index, matrix_row, col_no
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corp-code", action="append", required=True)
    parser.add_argument("--per-form", type=int, default=2, help="기업·서식마다 뽑을 행 수")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    with psycopg.connect(database_url()) as conn, conn.cursor() as cur:
        cur.execute(ROWS_SQL, (args.corp_code,))
        cells = cur.fetchall()
        # 표·행 단위로 묶는다: (corp, rcept, table, matrix_row) → 그 행의 셀들
        rows: dict[tuple, list] = defaultdict(list)
        for c in cells:
            rows[(c[0], c[1], c[2], c[9])].append(c)
        by_group: dict[tuple[str, str], list[tuple]] = defaultdict(list)
        for key, group in rows.items():
            by_group[(key[0], group[0][3])].append(key)
        picked: list[tuple] = []
        for (corp, form), keys in sorted(by_group.items()):
            latest = max(k[1] for k in keys)
            candidates = [k for k in keys if k[1] == latest]
            picked.extend(rng.sample(candidates, min(args.per_form, len(candidates))))
        evidence_ids = sorted({rows[k][0][16] for k in picked if rows[k][0][16]})
        cur.execute("SELECT evidence_id, content, corp_code FROM rag_evidence WHERE evidence_id = ANY(%s)", (evidence_ids,))
        chunks = {eid: content for eid, content, _ in cur.fetchall()}
        cur.execute("SELECT corp_code, corp_name FROM company WHERE corp_code = ANY(%s)", (args.corp_code,))
        names = dict(cur.fetchall())

    lines = ["# 서식 표 정형화 검수 표본", "", f"기업 {len(args.corp_code)}개, 서식·기업당 {args.per_form}행. 각 항목은 정형 값과 원문 청크의 같은 행을 나란히 둔다.",
             "검수자는 값·단위·연도·소속 법인이 원문과 같으면 **OK**, 다르면 무엇이 다른지 적는다.", ""]
    for number, key in enumerate(picked, start=1):
        group = rows[key]
        corp, rcept, table_index, matrix_row = key
        first = group[0]
        title = f"{names.get(corp, corp)} · {first[3]} · {first[4]}"
        lines.append(f"## {number}. {title}")
        lines.append("")
        lines.append(f"- 보고서 {rcept} · 표 {table_index} · 행렬 행 {matrix_row}" + (f" · 소속 법인 **{first[5]}**" if first[5] else "") + (f" · 단위 {first[6]}" if first[6] else ""))
        lines.append(f"- 행 이름: {' > '.join(first[10]) or '(없음)'}")
        lines.append("- 정형 값:")
        for c in group:
            year = f" ({c[12]}년)" if c[12] else ""
            num = f" → {c[13]:,.2f}".rstrip("0").rstrip(".") if c[13] is not None else ""
            lines.append(f"  - {c[11]}{year}: `{c[14]}`{num} [{c[15]}]")
        content = chunks.get(first[16])
        if content:
            body = [ln for ln in content.splitlines() if ln and not ln.startswith(("표 캡션:", "표 머리글:"))]
            header = next((ln for ln in content.splitlines() if ln.startswith("표 머리글:")), "")
            lines.append(f"- 원문 청크 `{first[16][-12:]}`: {header[:200]}")
            # 행 이름과 값 문자열이 가장 많이 겹치는 원문 줄을 고른다(rowspan 으로 같은 행 이름이 반복돼 첫 줄만 보면 틀린다).
            tokens = [t for t in [*first[10], *(c[14] for c in group)] if t and t != "-"]
            scored = sorted(body, key=lambda ln: -sum(1 for t in tokens if t in ln))
            best = scored[0] if scored and tokens and any(t in scored[0] for t in tokens) else None
            lines.append(f"  - 원문 행: {(best if best else '(같은 행을 찾지 못함)')[:300]}")
        else:
            lines.append("- 원문 청크: (현재 청크 DB 에 없음 — TU 재청킹 전 경계 차이)")
        lines.append("- 검수: ")
        lines.append("")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved: {args.out} ({len(picked)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
