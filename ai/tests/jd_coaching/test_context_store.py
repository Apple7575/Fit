import tempfile
import unittest
from pathlib import Path

from ai.jd_coaching.context_store import (
    InMemoryJobContextStore,
    JobContext,
    SqliteJobContextStore,
    make_source_hash,
)


def sample_context(context_id: str = "context-1") -> JobContext:
    return JobContext(
        context_id=context_id,
        source_hash=make_source_hash("기업", "직무", "JD 원문"),
        company_name="기업",
        position_name="직무",
        jd_text="JD 원문",
        role_elements=(
            {
                "role_element_id": "role-001",
                "name": "API 개발",
                "source_quote": "JD 원문",
                "evidence_section_ids": ["jd-role-001"],
                "evidence_requirements": [],
            },
        ),
        created_at="2026-09-13T00:00:00+00:00",
        job_posting_id="posting-1",
        source_url="https://careers.example.com/jobs/1",
        published_at="2026-09-01",
        valid_until="2026-09-30",
        retrieved_at="2026-09-13",
        source_type="OFFICIAL_CAREERS_SITE",
        version=1,
        source_filename="posting.pdf",
        source_content_sha256="a" * 64,
    )


class JobContextStoreContract:
    def make_store(self):
        raise NotImplementedError

    def test_saves_and_reads_context(self):
        store = self.make_store()
        context = sample_context()

        saved = store.save(context)

        self.assertEqual(saved, context)
        self.assertEqual(store.get(context.context_id), context)
        self.assertEqual(store.find_by_source_hash(context.source_hash), context)

    def test_same_source_hash_returns_existing_context(self):
        store = self.make_store()
        first = sample_context("context-1")
        second = sample_context("context-2")

        store.save(first)
        saved = store.save(second)

        self.assertEqual(saved.context_id, "context-1")

    def test_reports_latest_version_for_job_posting(self):
        store = self.make_store()
        first = sample_context("context-1")
        second = JobContext(
            **{
                **first.__dict__,
                "context_id": "context-2",
                "source_hash": make_source_hash("기업", "직무", "변경된 JD"),
                "jd_text": "변경된 JD",
                "version": 2,
            }
        )

        store.save(first)
        store.save(second)

        self.assertEqual(store.latest_version_for_job_posting("posting-1"), 2)
        self.assertEqual(store.latest_version_for_job_posting("missing"), 0)


class InMemoryJobContextStoreTest(JobContextStoreContract, unittest.TestCase):
    def make_store(self):
        return InMemoryJobContextStore()


class SqliteJobContextStoreTest(JobContextStoreContract, unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def make_store(self):
        return SqliteJobContextStore(Path(self.directory.name) / "contexts.db")


if __name__ == "__main__":
    unittest.main()
