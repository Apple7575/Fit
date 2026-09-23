"""전 종목 수집 대상 (팀 공통 기준 · 2,703개사).

`config/targets.csv` 의 10개사는 지표 파이프라인의 검증용 표본이다. 이 모듈은
그것과 별개로 **상장사 전체**를 다룬다 — 팀장 요청으로 사업보고서 원문(비정형)은
2,700여 개사를 대상으로 하고, 수치 데이터는 같은 모집단을 정형 API 로 받는다.

모집단 정의
    config/company_universe.csv 3,930개사 중 corp_cls 가 E(기타)가 아닌 것.

        Y 유가증권    829
        K 코스닥    1,768
        N 코넥스      106   합계 2,703
        E 기타      1,227   제외

**E 를 빼는 이유**는 정규 시장에 상장되지 않아 사업보고서 제출 의무와 재무제표
공시 범위가 다르기 때문이다. 팀장이 말한 "4천 중 2천7백"이 정확히 이 경계다.

`targets.csv` 와 달리 `listed_from` 이 없다. 상장 이전 연도를 미리 걸러낼 수단이
없으므로 **013(데이터 없음)을 결측이 아니라 정상 응답으로 세야 한다** — 86번이
"미상장을 수집 실패로 세면 커버리지가 왜곡된다"고 잡아낸 것과 같은 함정이다.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .paths import CONFIG

# 정규 시장. E(기타)는 제외한다.
LISTED_CLS = ("Y", "K", "N")

CLS_NAME = {"Y": "유가증권", "K": "코스닥", "N": "코넥스", "E": "기타"}

# 기업인수목적회사(스팩)는 **사업이 없는 껍데기**다. 합병할 회사를 찾을 목적만
# 가지고 상장하며, 우리 DB 실측이 그것을 그대로 보여 준다 (2026-09-22 · 운영 41곳).
#
#   매출 0원 (41곳 전부) · 직원 1~2명(임원뿐) · 시설투자 0건
#   자본 75억~122억은 공모로 모아 **신탁에 넣어 둔 돈**이다
#   부문 정보는 '관리 및 합병업무' 직원 수뿐이다
#
# **빼는 이유는 검색 오염보다 산업 평균 왜곡이 크다.** '금융 및 보험관련
# 서비스업'(66199) 28곳 중 27곳이 스팩이라, 그 업종 평균 직원수가 스팩을 넣으면
# 81명 · 빼면 1,198명이다(15배). 이 업종 실제 회사의 "업종 평균 대비" 비교가
# 지금 화면에서 무의미한 숫자로 나가고 있다.
#
# **이름으로 거른다.** 업종코드로는 갈라지지 않는다 — 66199·661 에 동국홀딩스·
# 효성·HDC 같은 지주회사와 다올투자증권·아주IB투자가 섞여 있다. 2026-09-22 실측에서
# 41곳 이름이 전부 `증권사 + N호 + 스팩` 이었고 오탐은 없었다. `기업인수목적` 으로
# 된 이름은 0건이라 이 한 규칙으로 다 걸린다.
#
# 스팩은 해마다 새로 상장되므로 명단에서 줄을 지우는 대신 **규칙으로 둔다** —
# DART 에서 명단을 다시 받아도 자동으로 걸러진다.
EXCLUDED_NAME = re.compile(r"스팩")


def is_excluded(corp_name: str) -> bool:
    """수집·시드·뉴스에서 모두 빼야 하는 회사인가.

    유니버스를 읽는 자리가 넷이다(`load_universe` · 시드 빌더 · 뉴스 매핑 ·
    뉴스 수집 드라이버). 한 곳만 고치면 나머지로 새므로 규칙을 여기 모은다.
    """
    return bool(EXCLUDED_NAME.search(corp_name or ""))


@dataclass(frozen=True)
class Company:
    corp_code: str
    corp_name: str
    stock_code: str
    corp_cls: str
    ksic_division: str
    division_name: str

    @property
    def market(self) -> str:
        return CLS_NAME.get(self.corp_cls, self.corp_cls)


def load_universe(path: Path | None = None, *,
                  listed_only: bool = True) -> list[Company]:
    """수집 대상 목록. 기본값은 정규 시장 상장사 2,703개사."""
    path = path or (CONFIG / "company_universe.csv")
    out: list[Company] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cls = (row.get("corp_cls") or "").strip()
            if listed_only and cls not in LISTED_CLS:
                continue
            if is_excluded(row.get("corp_name") or ""):
                continue
            out.append(Company(
                corp_code=row["corp_code"].strip(),
                corp_name=(row.get("corp_name") or "").strip(),
                stock_code=(row.get("stock_code") or "").strip(),
                corp_cls=cls,
                ksic_division=(row.get("ksic_division") or "").strip(),
                division_name=(row.get("division_name") or "").strip(),
            ))
    return out


def batches(companies: list[Company], size: int) -> list[list[Company]]:
    """다중회사 API 한 번에 넣을 묶음. size 는 실측으로 정한다."""
    return [companies[i:i + size] for i in range(0, len(companies), size)]
