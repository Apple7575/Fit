from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    corp_code: str
    source_type: str
    source_identity: str
    title: str
    content: str
    reference_period: str | None
    published_at: datetime
    source_url: str | None
    quality: str
    metadata: dict[str, object]
    content_hash: str
    source_updated_at: datetime | None

    def as_db_row(self) -> dict[str, object]:
        return {
            **asdict(self),
            "metadata": json.dumps(
                self.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
            ),
        }
