import tempfile
import unittest
from pathlib import Path

from ai.jd_coaching.analysis_store import (
    AnalysisJob,
    InMemoryAnalysisStore,
    SqliteAnalysisStore,
)


def sample_job() -> AnalysisJob:
    return AnalysisJob(
        analysis_id="analysis-1",
        context_id="context-1",
        status="QUEUED",
        documents=(
            {
                "document_id": "resume-1",
                "document_type": "RESUME",
                "text": "Python API를 개발했습니다.",
            },
        ),
        result=None,
        error=None,
        created_at="2026-09-13T00:00:00+00:00",
        updated_at="2026-09-13T00:00:00+00:00",
    )


class AnalysisStoreContract:
    def make_store(self):
        raise NotImplementedError

    def test_persists_status_result_and_error(self):
        store = self.make_store()
        job = sample_job()

        store.create(job)
        store.mark_running(job.analysis_id, "2026-09-13T00:01:00+00:00")
        running = store.get(job.analysis_id)
        self.assertEqual(running.status, "RUNNING")

        result = {"summary": {"supported": 1}}
        store.complete(job.analysis_id, result, "2026-09-13T00:02:00+00:00")
        completed = store.get(job.analysis_id)
        self.assertEqual(completed.status, "COMPLETED")
        self.assertEqual(completed.result, result)
        self.assertIsNone(completed.error)

        failed_job = AnalysisJob(
            **{**job.__dict__, "analysis_id": "analysis-2"}
        )
        store.create(failed_job)
        store.fail(
            failed_job.analysis_id,
            {"code": "ANALYSIS_FAILED", "message": "실패"},
            "2026-09-13T00:03:00+00:00",
        )
        failed = store.get(failed_job.analysis_id)
        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(failed.error["code"], "ANALYSIS_FAILED")


class InMemoryAnalysisStoreTest(AnalysisStoreContract, unittest.TestCase):
    def make_store(self):
        return InMemoryAnalysisStore()


class SqliteAnalysisStoreTest(AnalysisStoreContract, unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def make_store(self):
        return SqliteAnalysisStore(Path(self.directory.name) / "analyses.db")


if __name__ == "__main__":
    unittest.main()
