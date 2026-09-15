"""문자열·숫자 정규화 공통 유틸.

프로토타입 3개가 각자 조금씩 다른 `squash`/`to_num` 을 갖고 있었다. 미묘하게
달라서(음수 처리, 결측 토큰) 같은 원문을 다르게 읽을 수 있다. 여기로 합친다.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_NUM = re.compile(r"[\d,]+(?:\.\d+)?")
_DASHES = ("", "-", "–", "—")

# 원문에 **정의되지 않은 엔티티**가 그대로 들어 있다 — `&cr;` 하나로 487건에서
# 199번 나온다. 이걸 파서에 맡기면 libxml2 버전에 따라 지워지기도 하고 글자로
# 남기도 해서, 같은 문서가 환경마다 다르게 읽혔다 (S15P21A504-73 0차: 노트북
# libxml2 2.11.9 와 서버 2.14.6 이 487건 중 72건에서 갈렸다). 우리가 직접
# 치워서 어디서 돌리든 같은 값이 나오게 한다.
#
# 표준 엔티티(`&amp;` `&lt;` …)와 수치 참조(`&#39;`)는 건드리지 않는다. 파서가
# 이미 풀었어야 하는 것들이라, 글자로 남아 있다면 원문이 이중 이스케이프한
# 것이고 지우면 내용이 바뀐다.
_UNDEFINED_ENTITY = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#)[A-Za-z][A-Za-z0-9]{0,10};")

# 표 셀에 자간을 준 표기가 섞여 있다 — '엔 진 기 계' · '해 양 플 랜 트'.
# **전부 한 글자짜리 한글일 때만** 붙인다. '등 철강 제품' 처럼 진짜 낱말이
# 섞인 것은 건드리지 않는다.
_SPACED_HANGUL = re.compile(r"^[가-힣](?: [가-힣])+$")


def squash(s) -> str:
    """공백 정리. NBSP(\\xa0)를 먼저 없앤다 — DART 원문에 흔하다.

    미정의 엔티티와 자간 공백도 여기서 함께 정리한다. **셀 텍스트가 지나는
    길목이 이 함수 하나**라, 여기서 맞춰야 표를 고르는 단계까지 같은 값을 본다 —
    실제로 자간 때문에 표 점수가 갈려 노트북과 서버가 서로 다른 표를 고른
    문서가 있었다.

    엔티티는 **지운다**. 공백으로 바꾸면 libxml2 2.11.9 쪽과 갈린다 — 그쪽은
    파서가 엔티티를 이미 없앤 뒤라 그 자리에 공백이 없다. 우리가 공백을 넣으면
    `'자동차 부품및 기타'` 와 `'자동차 부품 및 기타'` 로 영영 어긋난다.
    """
    t = _UNDEFINED_ENTITY.sub("", str(s or "").replace("\xa0", " "))
    t = _WS.sub(" ", t).strip()
    return t.replace(" ", "") if _SPACED_HANGUL.match(t) else t


def norm(s) -> str:
    """공백·괄호·대괄호를 모두 제거한 비교용 키."""
    return re.sub(r"[\s\[\]()]+", "", squash(s))


def to_num(s, null_tokens: frozenset[str] | None = None) -> float | None:
    """문자열 → 수. 콤마·괄호음수·△·% 표기를 처리한다.

    괄호와 △ 는 회계 표기의 음수다. 이걸 놓치면 영업손실이 이익으로 뒤집힌다.
    """
    t = squash(s)
    if t in _DASHES or (null_tokens is not None and t in null_tokens):
        return None
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")")) or t.startswith("△")
    m = _NUM.search(t)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


def parse_tenure(s, null_tokens: frozenset[str] | None = None) -> float | None:
    """평균근속 → 연 단위 실수. '12.3' / '8년 6개월' / '4개월' 을 받는다.

    60을 넘는 값은 개월 수를 그대로 적은 것으로 본다(근속 60년은 현실적으로 없다).
    """
    t = squash(s)
    if t in _DASHES or (null_tokens is not None and t in null_tokens):
        return None
    if "년" in t or "개월" in t or "월" in t:
        y = re.search(r"(\d+(?:\.\d+)?)\s*년", t)
        mo = re.search(r"(\d+(?:\.\d+)?)\s*(?:개월|월)", t)
        if y or mo:
            return round(float(y.group(1)) if y else 0, 2) + (float(mo.group(1)) / 12 if mo else 0)
    v = to_num(t, null_tokens)
    if v is None:
        return None
    return round(v / 12, 2) if v > 60 else v
