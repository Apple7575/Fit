"""재검증과 재적재에 사용하는 기업별 사업보고서 청크 스테이징."""

from dataclasses import asdict
from datetime import datetime
import gzip
import json
import os
from pathlib import Path
from typing import Callable

from pipeline.rag_corpus.models import EvidenceRecord

from .models import EvidenceBatch


CHUNKING_VERSION = "business-report-structural-v2"
PARSER_REVISION = "table-rowspan-v2"


def stage_batch_lazy(
    staging_dir: Path, corp_code: str, build: Callable[[], EvidenceBatch], *, source_signature: str,
    chunking_version: str = CHUNKING_VERSION,
) -> dict[str, object]:
    records_path = staging_dir / f"{corp_code}.jsonl.gz"
    summary_path = staging_dir / f"{corp_code}.summary.json"
    reusable = _reusable_summary(summary_path, records_path, source_signature, chunking_version)
    if reusable is not None:
        return {**reusable, "write_status": "reused"}
    return stage_batch(
        staging_dir, corp_code, build(), source_signature=source_signature,
        chunking_version=chunking_version,
    )


def stage_batch(
    staging_dir: Path, corp_code: str, batch: EvidenceBatch, *, source_signature: str,
    chunking_version: str = CHUNKING_VERSION,
) -> dict[str, object]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    records_path = staging_dir / f"{corp_code}.jsonl.gz"
    summary_path = staging_dir / f"{corp_code}.summary.json"
    reusable = _reusable_summary(summary_path, records_path, source_signature, chunking_version)
    if reusable is not None:
        return {**reusable, "write_status": "reused"}

    temp_records = records_path.with_suffix(records_path.suffix + f".{os.getpid()}.tmp")
    with gzip.open(temp_records, "wt", encoding="utf-8", newline="\n") as output:
        for record in batch.records:
            output.write(json.dumps(_record_payload(record), ensure_ascii=False, sort_keys=True))
            output.write("\n")
    temp_records.replace(records_path)
    summary = {
        "corp_code": corp_code,
        "record_count": len(batch.records),
        "input_counts": dict(sorted(batch.input_counts.items())),
        "excluded_counts": dict(sorted(batch.excluded_counts.items())),
        "failures": list(batch.failures),
        "source_signature": source_signature,
        "chunking_version": chunking_version,
        "parser_revision": PARSER_REVISION,
        "records_path": str(records_path.resolve()),
    }
    temp_summary = summary_path.with_suffix(summary_path.suffix + f".{os.getpid()}.tmp")
    temp_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
    )
    temp_summary.replace(summary_path)
    return {**summary, "write_status": "staged"}


def read_staged_records(path: Path) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(_record_from_payload(json.loads(line)))
    return records


def _reusable_summary(
    summary_path: Path, records_path: Path, source_signature: str, chunking_version: str,
) -> dict[str, object] | None:
    if not summary_path.exists() or not records_path.exists():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if summary.get("source_signature") != source_signature:
        return None
    if summary.get("chunking_version") != chunking_version:
        return None
    if summary.get("parser_revision") != PARSER_REVISION:
        return None
    return summary


def _record_payload(record: EvidenceRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["published_at"] = record.published_at.isoformat()
    payload["source_updated_at"] = (
        record.source_updated_at.isoformat() if record.source_updated_at is not None else None
    )
    return payload


def _record_from_payload(payload: dict[str, object]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=str(payload["evidence_id"]), corp_code=str(payload["corp_code"]),
        source_type=str(payload["source_type"]), source_identity=str(payload["source_identity"]),
        title=str(payload["title"]), content=str(payload["content"]),
        reference_period=payload.get("reference_period"),
        published_at=datetime.fromisoformat(str(payload["published_at"])),
        source_url=payload.get("source_url"), quality=str(payload["quality"]),
        metadata=dict(payload.get("metadata") or {}), content_hash=str(payload["content_hash"]),
        source_updated_at=(
            datetime.fromisoformat(str(payload["source_updated_at"]))
            if payload.get("source_updated_at") is not None else None
        ),
    )
