"""청킹 실험에 사용할 고정 기업 표본을 선택한다."""

from __future__ import annotations

from hashlib import sha256


ANCHOR_CORP_CODES = (
    "00126380",  # 삼성전자
    "00164742",  # 현대자동차
    "00164779",  # SK하이닉스
    "00266961",  # NAVER
    "00356361",  # LG화학
)


def select_companies(
    companies: dict[str, dict[str, object]], *, size: int = 100, holdout_size: int = 20,
) -> list[dict[str, object]]:
    candidates = sorted(
        (
            (corp_code, int(company.get("record_count", 0)), len(company.get("failures", [])))
            for corp_code, company in companies.items()
            if int(company.get("record_count", 0)) > 0
        ),
        key=lambda item: (item[1], item[0]),
    )
    if size <= 0 or holdout_size < 0 or holdout_size > size:
        raise ValueError("표본 크기와 홀드아웃 크기를 확인하세요")
    if len(candidates) < size:
        raise ValueError(f"사용 가능한 기업이 {size}개보다 적습니다")

    by_code = {corp_code: item for corp_code, *item in candidates}
    selected: dict[str, str] = {}

    def add(corp_code: str, reason: str) -> None:
        if corp_code in by_code and len(selected) < size:
            selected.setdefault(corp_code, reason)

    for corp_code in ANCHOR_CORP_CODES:
        add(corp_code, "anchor")

    failed = sorted(candidates, key=lambda item: (-item[2], -item[1], item[0]))
    for corp_code, _, failure_count in failed:
        if failure_count == 0:
            break
        if sum(reason == "source-failure" for reason in selected.values()) >= 20:
            break
        add(corp_code, "source-failure")

    for corp_code, _, _ in candidates[:15]:
        add(corp_code, "low-volume")
    for corp_code, _, _ in reversed(candidates[-15:]):
        add(corp_code, "high-volume")

    remaining = [item for item in candidates if item[0] not in selected]
    needed = size - len(selected)
    if needed:
        for index in range(needed):
            position = round(index * (len(remaining) - 1) / max(needed - 1, 1))
            add(remaining[position][0], "volume-quantile")

    if len(selected) < size:
        for corp_code, _, _ in candidates:
            add(corp_code, "deterministic-fill")

    holdout_codes = {
        corp_code
        for corp_code in sorted(
            selected,
            key=lambda code: sha256(f"company-rag-holdout-v1:{code}".encode()).digest(),
        )[:holdout_size]
    }
    result = []
    for corp_code, reason in selected.items():
        record_count, failure_count = by_code[corp_code]
        result.append({
            "corp_code": corp_code,
            "group": "holdout" if corp_code in holdout_codes else "tuning",
            "selection_reason": reason,
            "baseline_record_count": record_count,
            "baseline_failure_count": failure_count,
        })
    return result
