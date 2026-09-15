"""문자열·숫자 정규화 공통 유틸.

프로토타입 3개가 각자 조금씩 다른 `squash`/`to_num` 을 갖고 있었다. 미묘하게
달라서(음수 처리, 결측 토큰) 같은 원문을 다르게 읽을 수 있다. 여기로 합친다.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_NUM = re.compile(r"[\d,]+(?:\.\d+)?")
_DASHES = ("", "-", "–", "—")


def squash(s) -> str:
    """공백 정리. NBSP(\\xa0)를 먼저 없앤다 — DART 원문에 흔하다."""
    return _WS.sub(" ", str(s or "").replace("\xa0", " ")).strip()


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
