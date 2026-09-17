"""CSV 읽기·쓰기 한 곳.

인코딩 규칙 (data/docs/DATA_STORAGE_STANDARD.md 6장)

- **curated 시드는 BOM 없는 UTF-8.** `COPY ... WITH (FORMAT csv, ENCODING 'UTF8')` 가
  BOM 을 첫 컬럼명의 일부로 읽어 헤더 대조가 깨진다.
- **staged 는 BOM 없는 UTF-8.** 적재 입력이 아니라 기계가 다시 읽는 중간 산출물이다.
- 기존 `_out/*.csv` 와 `data/*.csv` 는 BOM 이 붙어 있다(사람이 Excel 로 보는 산출물).
  읽을 때는 `utf-8-sig` 로 열어 두 경우를 모두 받는다.

줄바꿈은 `\n` 으로 고정한다. Windows 기본값(`\r\n`)으로 쓰면 같은 입력인데도 OS 마다
체크섬이 달라져 재현 검증(§11-13)이 통과하지 못한다.
"""
from __future__ import annotations

import csv
from pathlib import Path


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> int:
    """BOM 없는 UTF-8, LF 줄바꿈으로 쓴다. 없는 키는 빈 셀, 남는 키는 버린다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in fields})
    return len(rows)


def _cell(value) -> str:
    """None 은 빈 셀. 빈 셀이 DB 의 NULL 이다 (기준 문서 6장의 null 표현)."""
    return "" if value is None else str(value)


def read_csv(path: Path) -> list[dict]:
    """BOM 이 있어도 없어도 읽는다."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return next(csv.reader(stream), [])


def row_count(path: Path) -> int:
    """헤더를 뺀 데이터 행 수. 셀 안의 줄바꿈을 세지 않도록 csv 로 읽는다."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        return sum(1 for _ in reader)
