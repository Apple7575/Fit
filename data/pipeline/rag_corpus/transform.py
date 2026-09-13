from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable, Mapping

from .models import EvidenceRecord


_RECEIPT_NUMBER = re.compile(r"^[0-9]{14}$")
_ATTR_TITLES = {
    "main_business": "주요 사업",
    "main_product": "주요 제품",
    "business_keyword": "핵심 사업 키워드",
    "new_business": "신규 사업",
    "strategy_change": "사업 전략 변화",
    "rd_field": "연구 분야",
}


def stable_evidence_id(source_identity: str) -> str:
    """원천 자연키만으로 재실행에도 변하지 않는 식별자를 만든다."""
    source_name = source_identity.split(":", 1)[0].replace("_", "-")
    digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:32]
    return f"{source_name}-{digest}"


def content_hash(payload: Mapping[str, object]) -> str:
    """레코드 생성 전의 정규화 payload를 해시한다."""
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def profile_record(row: Mapping[str, object]) -> EvidenceRecord:
    corp_code = _required(row, "corp_code")
    corp_name = _required(row, "corp_name")
    source_updated_at = _source_updated_at(row)
    dart_date = _calendar_date(row.get("dart_modify_date"))
    if dart_date is not None:
        published_at = _midnight(dart_date)
        date_inferred = False
    elif source_updated_at is not None:
        published_at = source_updated_at
        date_inferred = False
    else:
        raise ValueError("기업 기본 정보에 공개 시점이 없습니다")

    details = []
    for key, label in (
        ("corp_cls", "시장 구분"),
        ("industry_code", "산업 코드"),
        ("ceo_nm", "대표자"),
        ("established_date", "설립일"),
        ("listed_date", "상장일"),
    ):
        value = _present(row.get(key))
        if value is not None:
            details.append(f"{label} {value}")
    content = f"{corp_name}는 " + (", ".join(details) + "입니다" if details else "기본 정보가 공시되었습니다") + "."
    metadata = _without_none({
        "corp_cls": row.get("corp_cls"),
        "industry_code": row.get("industry_code"),
        "dart_modify_date": row.get("dart_modify_date"),
        "date_inferred": date_inferred,
    })
    return _build_record(
        corp_code=corp_code,
        source_type="COMPANY_PROFILE",
        source_identity=f"company:{corp_code}",
        title=f"{corp_name} 기업 기본 정보",
        content=content,
        reference_period=None,
        published_at=published_at,
        source_url=_present(row.get("homepage_url")),
        quality="PRIMARY",
        metadata=metadata,
        source_updated_at=source_updated_at,
    )


def metric_record(row: Mapping[str, object]) -> EvidenceRecord | None:
    verdict = _present(row.get("verdict"))
    if verdict not in ("verified", "unverified"):
        return None
    corp_code = _required(row, "corp_code")
    corp_name = _required(row, "corp_name")
    fiscal_year = _year(row)
    metric_code = _required(row, "metric_code")
    metric_name = _present(row.get("metric_name")) or metric_code
    metric_value = _present(row.get("metric_value"))
    if metric_value is None:
        return None
    unit = _present(row.get("unit"))
    published_at, date_inferred, receipt_no = _publication_date(row.get("rcept_no"), fiscal_year)
    value = str(metric_value) + (f" {unit}" if unit is not None else "")
    metadata = _without_none({
        "metric_code": metric_code,
        "unit": unit,
        "rcept_no": receipt_no,
        "date_inferred": date_inferred,
    })
    return _build_record(
        corp_code=corp_code,
        source_type="COMPANY_METRIC",
        source_identity=f"company_metric:{corp_code}:{fiscal_year}:{metric_code}",
        title=f"{corp_name} {fiscal_year}년 {metric_name}",
        content=f"{corp_name}의 {fiscal_year}년 {metric_name}은 {value}입니다.",
        reference_period=str(fiscal_year),
        published_at=published_at,
        source_url=None,
        quality="VERIFIED" if verdict == "verified" else "UNVERIFIED",
        metadata=metadata,
        source_updated_at=_source_updated_at(row),
    )


def text_records(rows: Iterable[Mapping[str, object]]) -> list[EvidenceRecord]:
    groups: dict[tuple[str, int, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if _present(row.get("generated_at")) is not None or _present(row.get("value_text")) is None:
            continue
        try:
            key = (_required(row, "corp_code"), _year(row), _required(row, "attr_key"))
        except ValueError:
            continue
        groups[key].append(row)

    records = []
    for (corp_code, fiscal_year, attr_key), members in sorted(groups.items()):
        ordered = sorted(members, key=lambda row: (_sequence(row), str(_present(row.get("value_text")))))
        corp_name = _required(ordered[0], "corp_name")
        values = [str(_present(row.get("value_text"))) for row in ordered]
        title = _ATTR_TITLES.get(attr_key, attr_key)
        source_updated_at = _latest_source_updated_at(ordered)
        records.append(_build_record(
            corp_code=corp_code,
            source_type="COMPANY_TEXT",
            source_identity=f"company_text:{corp_code}:{fiscal_year}:{attr_key}",
            title=f"{corp_name} {fiscal_year}년 {title}",
            content=f"{corp_name}의 {fiscal_year}년 {title}은 {', '.join(values)}입니다.",
            reference_period=str(fiscal_year),
            published_at=_inferred_fiscal_date(fiscal_year),
            source_url=None,
            quality="PRIMARY",
            metadata={"attr_key": attr_key, "item_count": len(values), "date_inferred": True},
            source_updated_at=source_updated_at,
        ))
    return records


def segment_records(rows: Iterable[Mapping[str, object]]) -> list[EvidenceRecord]:
    groups: dict[tuple[str, int, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if _present(row.get("metric_value")) is None:
            continue
        if _present(row.get("verdict")) in ("rejected", "not_found"):
            continue
        try:
            key = (_required(row, "corp_code"), _year(row), _required(row, "segment_name"))
        except ValueError:
            continue
        groups[key].append(row)

    records = []
    for (corp_code, fiscal_year, segment_name), members in sorted(groups.items()):
        ordered = sorted(members, key=lambda row: _required(row, "metric_code"))
        corp_name = _required(ordered[0], "corp_name")
        parts = []
        for row in ordered:
            metric_name = _present(row.get("metric_name")) or _required(row, "metric_code")
            unit = _present(row.get("unit"))
            parts.append(f"{metric_name} {row['metric_value']}" + (f" {unit}" if unit is not None else ""))
        publication_dates = [
            _publication_date(row.get("rcept_no"), fiscal_year) for row in ordered
        ]
        published_at, date_inferred, receipt_no = max(
            publication_dates, key=lambda candidate: (candidate[0], not candidate[1])
        )
        metric_metadata = [
            _without_none({"metric_code": _required(row, "metric_code"), "unit": _present(row.get("unit"))})
            for row in ordered
        ]
        records.append(_build_record(
            corp_code=corp_code,
            source_type="SEGMENT_METRIC",
            source_identity=f"segment_metric:{corp_code}:{fiscal_year}:{segment_name}",
            title=f"{corp_name} {fiscal_year}년 {segment_name} 부문 지표",
            content=f"{corp_name}의 {fiscal_year}년 {segment_name} 부문은 {', '.join(parts)}입니다.",
            reference_period=str(fiscal_year),
            published_at=published_at,
            source_url=None,
            quality=_group_quality(ordered),
            metadata=_without_none({"segment_name": segment_name, "metrics": metric_metadata,
                                    "rcept_no": receipt_no, "date_inferred": date_inferred}),
            source_updated_at=_latest_source_updated_at(ordered),
        ))
    return records


def activity_record(row: Mapping[str, object]) -> EvidenceRecord:
    corp_code = _required(row, "corp_code")
    corp_name = _required(row, "corp_name")
    fiscal_year = _year(row)
    activity_type = _required(row, "activity_type")
    published_at, date_inferred, receipt_no = _publication_date(row.get("rcept_no"), fiscal_year)
    parts = [activity_type]
    for key, label in (("field_name", None), ("purpose", None), ("amount", "금액"), ("counterparty", "상대방")):
        value = _present(row.get(key))
        if value is not None:
            parts.append(str(value) if label is None else f"{label} {value}")
    identity = _activity_identity(row, corp_code, fiscal_year, activity_type)
    metadata = _without_none({
        "activity_type": activity_type,
        "field_name": row.get("field_name"),
        "purpose": row.get("purpose"),
        "amount": row.get("amount"),
        "counterparty": row.get("counterparty"),
        "rcept_no": receipt_no,
        "date_inferred": date_inferred,
    })
    return _build_record(
        corp_code=corp_code,
        source_type="COMPANY_ACTIVITY",
        source_identity=identity,
        title=f"{corp_name} {fiscal_year}년 {activity_type} 활동",
        content=f"{corp_name}의 {fiscal_year}년 {activity_type} 활동은 {', '.join(parts[1:]) if len(parts) > 1 else activity_type}입니다.",
        reference_period=str(fiscal_year),
        published_at=published_at,
        source_url=None,
        quality="PRIMARY",
        metadata=metadata,
        source_updated_at=_source_updated_at(row),
    )


def _build_record(*, corp_code: str, source_type: str, source_identity: str, title: str,
                  content: str, reference_period: str | None, published_at: datetime,
                  source_url: str | None, quality: str, metadata: dict[str, object],
                  source_updated_at: datetime | None) -> EvidenceRecord:
    hash_payload = {
        "title": title,
        "content": content,
        "reference_period": reference_period,
        "source_url": source_url,
        "quality": quality,
        "metadata": metadata,
    }
    return EvidenceRecord(
        evidence_id=stable_evidence_id(source_identity),
        corp_code=corp_code,
        source_type=source_type,
        source_identity=source_identity,
        title=title,
        content=content,
        reference_period=reference_period,
        published_at=published_at,
        source_url=source_url,
        quality=quality,
        metadata=metadata,
        content_hash=content_hash(hash_payload),
        source_updated_at=source_updated_at,
    )


def _publication_date(receipt_no: object, fiscal_year: int) -> tuple[datetime, bool, str | None]:
    receipt = _present(receipt_no)
    if receipt is not None and _RECEIPT_NUMBER.fullmatch(receipt):
        receipt_date = _calendar_date(receipt[:8])
        if receipt_date is not None:
            return _midnight(receipt_date), False, receipt
    return _inferred_fiscal_date(fiscal_year), True, None


def _inferred_fiscal_date(fiscal_year: int) -> datetime:
    return datetime(fiscal_year + 1, 4, 1, tzinfo=timezone.utc)


def _calendar_date(value: object) -> date | None:
    text = _present(value)
    if text is None or not re.fullmatch(r"[0-9]{8}", text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _midnight(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _source_updated_at(row: Mapping[str, object]) -> datetime | None:
    return _as_datetime(row.get("source_updated_at") or row.get("updated_at"))


def _latest_source_updated_at(rows: Iterable[Mapping[str, object]]) -> datetime | None:
    values = [value for value in (_source_updated_at(row) for row in rows) if value is not None]
    return max(values) if values else None


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return _midnight(value)
    text = _present(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _group_quality(rows: Iterable[Mapping[str, object]]) -> str:
    verdicts = {_present(row.get("verdict")) for row in rows}
    if "unverified" in verdicts:
        return "UNVERIFIED"
    if verdicts == {"verified"}:
        return "VERIFIED"
    return "PRIMARY"


def _activity_identity(row: Mapping[str, object], corp_code: str, fiscal_year: int, activity_type: str) -> str:
    identifier = _present(row.get("id"))
    if identifier is not None:
        return f"company_activity:{corp_code}:{identifier}"
    natural_key = ":".join(str(_present(row.get(key)) or "-") for key in (
        "rcept_no", "field_name", "purpose", "amount", "counterparty"
    ))
    return f"company_activity:{corp_code}:{fiscal_year}:{activity_type}:{natural_key}"


def _year(row: Mapping[str, object]) -> int:
    value = row.get("fiscal_year")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError("fiscal_year가 필요합니다") from None


def _sequence(row: Mapping[str, object]) -> int:
    try:
        return int(row.get("seq", 0))
    except (TypeError, ValueError):
        return 0


def _required(row: Mapping[str, object], key: str) -> str:
    value = _present(row.get(key))
    if value is None:
        raise ValueError(f"{key}가 필요합니다")
    return value


def _present(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _without_none(values: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if _present(value) is not None or isinstance(value, bool)}
