from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.rag_corpus.models import EvidenceRecord
from pipeline.raw_sources.models import EvidenceBatch
from pipeline.raw_sources.staging import read_staged_records, stage_batch, stage_batch_lazy


class StagingTest(unittest.TestCase):
    def test_stage_batch_round_trips_records_and_reuses_completed_company(self):
        record = EvidenceRecord(
            evidence_id="ev-1", corp_code="00000001", source_type="DART_BUSINESS_REPORT",
            source_identity="source-1", title="제목", content="내용", reference_period="2024",
            published_at=datetime(2025, 3, 18, tzinfo=timezone.utc), source_url=None,
            quality="PRIMARY", metadata={"content_type": "TEXT"}, content_hash="hash",
            source_updated_at=None,
        )
        batch = EvidenceBatch([record], {"documents": 1}, {"blank_content": 2})
        with tempfile.TemporaryDirectory() as directory:
            first = stage_batch(Path(directory), "00000001", batch, source_signature="archive-v1")
            second = stage_batch(Path(directory), "00000001", batch, source_signature="archive-v1")
            restored = read_staged_records(Path(first["records_path"]))

        self.assertEqual(first["write_status"], "staged")
        self.assertEqual(second["write_status"], "reused")
        self.assertEqual(restored, [record])

    def test_stage_batch_lazy_does_not_build_an_already_completed_company(self):
        empty = EvidenceBatch([], {"documents": 0}, {})
        with tempfile.TemporaryDirectory() as directory:
            staging_dir = Path(directory)
            stage_batch(staging_dir, "00000001", empty, source_signature="archive-v1")

            reused = stage_batch_lazy(
                staging_dir, "00000001",
                lambda: self.fail("완료된 기업을 다시 파싱하면 안 됩니다"),
                source_signature="archive-v1",
            )

        self.assertEqual(reused["write_status"], "reused")

    def test_chunking_version_separates_reusable_results(self):
        empty = EvidenceBatch([], {}, {})
        with tempfile.TemporaryDirectory() as directory:
            staging_dir = Path(directory)
            first = stage_batch(
                staging_dir, "00000001", empty, source_signature="archive-v1",
                chunking_version="structural-800-v1",
            )
            second = stage_batch_lazy(
                staging_dir, "00000001", lambda: empty, source_signature="archive-v1",
                chunking_version="adaptive-v1",
            )

        self.assertEqual(first["chunking_version"], "structural-800-v1")
        self.assertEqual(second["chunking_version"], "adaptive-v1")
        self.assertEqual(second["write_status"], "staged")

    def test_parser_revision_rebuilds_old_staging_with_same_profile(self):
        empty = EvidenceBatch([], {}, {})
        with tempfile.TemporaryDirectory() as directory:
            staging_dir = Path(directory)
            stage_batch(
                staging_dir, "00000001", empty, source_signature="archive-v1",
                chunking_version="adaptive-v1",
            )
            summary_path = staging_dir / "00000001.summary.json"
            old_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            old_summary.pop("parser_revision", None)
            summary_path.write_text(json.dumps(old_summary), encoding="utf-8")

            rebuilt = stage_batch_lazy(
                staging_dir, "00000001", lambda: empty,
                source_signature="archive-v1", chunking_version="adaptive-v1",
            )

        self.assertEqual(rebuilt["write_status"], "staged")
