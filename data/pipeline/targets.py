"""수집 대상 목록.

`config/targets.csv` 를 읽는다. 컬럼은 다음과 같다.

    ksic_division,corp_code,stock_code,display_name,corp_name,listed_from

`listed_from` 은 상장연도다. 비어 있으면 "이전부터 상장"으로 본다.
이 값이 있으면 그 이전 연도는 **호출하지 않는다** — 어차피 013 이 오고,
"수집 실패"와 "미상장"을 로그에서 구분해야 하기 때문이다.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .paths import CONFIG


@dataclass(frozen=True)
class Target:
    corp_code: str
    display_name: str        # 화면 표시용  '엔씨소프트'
    corp_name: str           # DART 등록명  '(주)엔씨'
    stock_code: str
    ksic_division: str
    listed_from: int | None  # 상장연도. None 이면 제약 없음

    def is_listed(self, year: int) -> bool:
        return self.listed_from is None or year >= self.listed_from


def load_targets(path: Path | None = None) -> list[Target]:
    path = path or (CONFIG / "targets.csv")
    out: list[Target] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw_year = (row.get("listed_from") or "").strip()
            out.append(Target(
                corp_code=row["corp_code"].strip(),
                display_name=row["display_name"].strip(),
                corp_name=(row.get("corp_name") or "").strip(),
                stock_code=(row.get("stock_code") or "").strip(),
                ksic_division=(row.get("ksic_division") or "").strip(),
                listed_from=int(raw_year) if raw_year else None,
            ))
    return out


def by_corp_code(targets: list[Target]) -> dict[str, Target]:
    return {t.corp_code: t for t in targets}
