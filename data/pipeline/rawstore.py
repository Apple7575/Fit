"""원본 저장소 읽기 전용 접근자.

정규화 계층은 **API 를 호출하지 않는다.** 수집(WP-5)이 받아둔 `.cache/` 파일만
읽는다. 그래서 `DartClient` 가 아니라 이 클래스를 쓴다 — 네트워크로 나갈
수단 자체가 없어야 계층 분리가 말이 아니라 코드로 강제된다.

원본이 없으면 `RawMissing` 을 올린다. 정규화는 그걸 "수집이 안 된 것"으로
기록하고 다음 지표로 넘어간다. 여기서 몰래 받아오면 안 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import cache_dir


class RawMissing(FileNotFoundError):
    """원본이 캐시에 없다. 수집(WP-5)을 먼저 돌려야 한다."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"원본 없음: {name} — scripts/collect.py 를 먼저 실행하라")


class RawStore:
    def __init__(self, cache: Path | None = None):
        self.cache = cache or cache_dir()

    # ------------------------------------------------------------- 저수준

    def path(self, name: str) -> Path:
        p = self.cache / name
        if not p.exists():
            raise RawMissing(name)
        return p

    def json(self, name: str) -> dict:
        return json.loads(self.path(name).read_text(encoding="utf-8"))

    def rows(self, name: str) -> list[dict]:
        """응답의 list. 013(데이터 없음)이면 빈 리스트."""
        return self.json(name).get("list") or []

    def exists(self, name: str) -> bool:
        return (self.cache / name).exists()

    # --------------------------------------------------------- 엔드포인트별

    def single_acnt(self, corp_code: str, year: int) -> list[dict]:
        """주요계정. 행에 fs_div 가 있다 — 연결·별도가 섞여 온다."""
        return self.rows(f"fnlttSinglAcnt_{corp_code}_{year}.json")

    def single_acnt_all(self, corp_code: str, year: int, fs_div: str) -> list[dict]:
        """전체재무제표. 행에 fs_div 가 없다 — 무엇을 요청했는지는 파일명에만 있다."""
        return self.rows(f"fnlttSinglAcntAll_{corp_code}_{year}_{fs_div}.json")

    def emp_status(self, corp_code: str, year: int) -> list[dict]:
        return self.rows(f"empSttus_{corp_code}_{year}.json")

    def document(self, rcept_no: str) -> Path:
        return self.path(f"document_{rcept_no}.xml")
