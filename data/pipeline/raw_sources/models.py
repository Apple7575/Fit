from __future__ import annotations

from dataclasses import dataclass

from pipeline.rag_corpus.models import EvidenceRecord


@dataclass(frozen=True)
class EvidenceBatch:
    records: list[EvidenceRecord]
    input_counts: dict[str, int]
    excluded_counts: dict[str, int]
    failures: tuple[dict[str, str], ...] = ()
