from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SOURCE_TYPES = {
    "JOB_POSTING",
    "OFFICIAL_JOB_DESCRIPTION",
    "TALENT_PROFILE",
}
SOURCE_STATUSES = {"ACCESSIBLE", "ARCHIVED", "UNKNOWN"}
SECTION_TYPES = {
    "JOB_SUMMARY",
    "RESPONSIBILITY",
    "REQUIRED_QUALIFICATION",
    "PREFERRED_QUALIFICATION",
    "TALENT_VALUE",
    "OTHER",
}


class DataContractError(ValueError):
    """입력 문서가 JD 데이터 계약을 충족하지 못한 경우."""


@dataclass(frozen=True)
class JdSection:
    section_id: str
    section_type: str
    ordinal: int
    text: str
    source_page: int | None


@dataclass(frozen=True)
class JdDocument:
    schema_version: str
    document_id: str
    company_name: str
    organization: str | None
    job_title: str | None
    source_type: str
    source_url: str
    retrieved_at: date
    published_at: date | None
    valid_until: date | None
    source_status: str
    source_file_name: str | None
    source_file_sha256: str | None
    sections: tuple[JdSection, ...]


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DataContractError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DataContractError(f"{field} must be null or a non-empty string")
    return value.strip()


def _parse_date(payload: dict[str, Any], field: str, *, required: bool) -> date | None:
    value = payload.get(field)
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise DataContractError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DataContractError(f"{field} must be an ISO date") from exc


def _parse_sections(payload: dict[str, Any]) -> tuple[JdSection, ...]:
    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise DataContractError("sections must be a non-empty list")

    sections: list[JdSection] = []
    section_ids: set[str] = set()
    ordinals: set[int] = set()
    for raw in raw_sections:
        if not isinstance(raw, dict):
            raise DataContractError("each section must be an object")
        section_id = _required_text(raw, "section_id")
        if section_id in section_ids:
            raise DataContractError(f"duplicate section_id: {section_id}")
        section_ids.add(section_id)

        section_type = _required_text(raw, "section_type")
        if section_type not in SECTION_TYPES:
            raise DataContractError(f"unknown section_type: {section_type}")

        ordinal = raw.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            raise DataContractError("ordinal must be a positive integer")
        if ordinal in ordinals:
            raise DataContractError(f"duplicate ordinal: {ordinal}")
        ordinals.add(ordinal)

        sections.append(
            JdSection(
                section_id=section_id,
                section_type=section_type,
                ordinal=ordinal,
                text=_required_text(raw, "text"),
                source_page=_parse_source_page(raw),
            )
        )
    return tuple(sorted(sections, key=lambda section: section.ordinal))


def _parse_source_page(payload: dict[str, Any]) -> int | None:
    value = payload.get("source_page")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise DataContractError("source_page must be null or a positive integer")
    return value


def parse_jd_document(payload: dict[str, Any]) -> JdDocument:
    if not isinstance(payload, dict):
        raise DataContractError("document must be an object")

    schema_version = _required_text(payload, "schema_version")
    if schema_version != "1.0":
        raise DataContractError(f"unsupported schema_version: {schema_version}")

    source_type = _required_text(payload, "source_type")
    if source_type not in SOURCE_TYPES:
        raise DataContractError(f"unknown source_type: {source_type}")

    source_status = _required_text(payload, "source_status")
    if source_status not in SOURCE_STATUSES:
        raise DataContractError(f"unknown source_status: {source_status}")

    source_url = _required_text(payload, "source_url")
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise DataContractError("source_url must be an absolute HTTPS URL")

    retrieved_at = _parse_date(payload, "retrieved_at", required=True)
    published_at = _parse_date(payload, "published_at", required=False)
    valid_until = _parse_date(payload, "valid_until", required=False)
    if published_at and valid_until and valid_until < published_at:
        raise DataContractError("valid_until must not precede published_at")

    source_file_sha256 = _optional_text(payload, "source_file_sha256")
    if source_file_sha256 is not None and (
        len(source_file_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in source_file_sha256)
    ):
        raise DataContractError("source_file_sha256 must be a 64-character hex string")

    return JdDocument(
        schema_version=schema_version,
        document_id=_required_text(payload, "document_id"),
        company_name=_required_text(payload, "company_name"),
        organization=_optional_text(payload, "organization"),
        job_title=_optional_text(payload, "job_title"),
        source_type=source_type,
        source_url=source_url,
        retrieved_at=retrieved_at,
        published_at=published_at,
        valid_until=valid_until,
        source_status=source_status,
        source_file_name=_optional_text(payload, "source_file_name"),
        source_file_sha256=source_file_sha256,
        sections=_parse_sections(payload),
    )


def load_jd_document(path: Path) -> JdDocument:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataContractError(f"cannot read JD document: {path.name}") from exc
    return parse_jd_document(payload)
