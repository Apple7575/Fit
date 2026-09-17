from contextlib import contextmanager
from datetime import datetime, timezone
import unittest

import numpy as np

from pipeline.rag_corpus.embedding_build import (
    EmbeddingBuildError, EmbeddingBuildRepository, build_embeddings,
)


def pending_rows(count):
    return [dict(evidence_id=f"e{index}", company_name="기업", corp_code="00126380",
                 source_type="COMPANY_TEXT", title="사업", published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 content=f"본문{index}", source_url=None, reference_period="2025",
                 quality="PRIMARY", metadata={}, content_hash=str(index) * 64)
            for index in range(count)]


class FakeFactory:
    def __init__(self, rows):
        self.rows = rows
        self.stored = {}
        self.executed = []
        self.active = 0
        self.committed_batches = 0
        self.fail_write = False

    @contextmanager
    def __call__(self):
        connection = FakeConnection(self)
        self.active += 1
        try:
            yield connection
            if connection.writes:
                self.stored.update(connection.writes)
                self.committed_batches += 1
        finally:
            self.active -= 1


class FakeConnection:
    def __init__(self, factory):
        self.factory = factory
        self.writes = {}

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params=()):
        self.factory.executed.append((sql, params))
        if sql.startswith("INSERT"):
            if self.factory.fail_write:
                raise RuntimeError("database secret")
            self.writes[(params[0], params[1], params[2])] = params
            return
        model, version = params[:2]
        filtered = self.factory.rows
        index = 2
        if "e.corp_code = ANY" in sql:
            filtered = [r for r in filtered if r['corp_code'] in params[index]]
            index += 1
        if "e.source_type = ANY" in sql:
            filtered = [r for r in filtered if r['source_type'] in params[index]]
            index += 1
        pending = [r for r in filtered if self.factory.stored.get(
            (r['evidence_id'], model, version), (None, None, None, None))[3] != r['content_hash']]
        if "COUNT(*)" in sql:
            self.result = [(len(pending), len(filtered) - len(pending))]
        else:
            if "(e.corp_code, e.evidence_id) >" in sql:
                pending = [r for r in pending if (r['corp_code'], r['evidence_id']) > tuple(params[index:index + 2])]
            self.result = sorted(pending, key=lambda r: (r['corp_code'], r['evidence_id']))[:params[-1]]

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0]


class FakeEncoder:
    def __init__(self, factory, fail_batch=None, vectors=None):
        self.factory = factory
        self.passage_inputs = []
        self.fail_batch = fail_batch
        self.vectors = vectors

    def embed_passages(self, texts):
        assert self.factory.active == 0, "DB transaction held during embedding"
        self.passage_inputs.append(texts)
        if len(self.passage_inputs) == self.fail_batch:
            raise RuntimeError("model secret")
        return np.array(self.vectors if self.vectors is not None else [[3., 4.]] * len(texts))


class EmbeddingBuildTests(unittest.TestCase):
    def run_build(self, factory, encoder=None, **kwargs):
        return build_embeddings(factory, encoder, model="e5", version="document-v1",
                                corp_codes=None, batch_size=2, dry_run=False, **kwargs)

    def test_pending_query_filters_model_version_hash_and_uses_keyset(self):
        factory = FakeFactory([])
        EmbeddingBuildRepository(FakeConnection(factory)).pending(
            "e5", "v2", ["00126380"], ["DART_BUSINESS_REPORT"],
            batch_size=2, after=("00126380", "e1"),
        )
        sql, params = factory.executed[0]
        self.assertIn("LEFT JOIN rag_evidence_embedding", sql)
        self.assertIn("re.embedding_model = %s", sql)
        self.assertIn("re.embedding_version = %s", sql)
        self.assertIn("re.content_hash <> e.content_hash", sql)
        self.assertIn("re.evidence_id IS NULL", sql)
        self.assertIn("ORDER BY e.corp_code, e.evidence_id", sql)
        self.assertIn("(e.corp_code, e.evidence_id) > (%s, %s)", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertIn("e.source_type = ANY(%s)", sql)
        self.assertEqual(params, [
            "e5", "v2", ["00126380"], ["DART_BUSINESS_REPORT"],
            "00126380", "e1", 2,
        ])

    def test_batches_persist_normalized_vectors_and_rerun_skips_committed_rows(self):
        factory = FakeFactory(pending_rows(3))
        encoder = FakeEncoder(factory)
        summary = self.run_build(factory, encoder)
        self.assertEqual((summary.selected, summary.embedded, summary.failed, summary.dimension), (3, 3, 0, 2))
        self.assertEqual([len(batch) for batch in encoder.passage_inputs], [2, 1])
        self.assertEqual(encoder.passage_inputs[0][0], "기업: 기업\n자료 유형: COMPANY_TEXT\n제목: 사업\n기준 기간: 2025\n발행일: 2026-01-01T00:00:00+00:00\n본문: 본문0")
        self.assertEqual(factory.committed_batches, 2)
        self.assertEqual(factory.stored[("e0", "e5", "document-v1")][-1], bytes.fromhex("9a99193fcdcc4c3f"))
        rerun = self.run_build(factory, encoder)
        self.assertEqual((rerun.selected, rerun.embedded, rerun.unchanged), (0, 0, 3))
        self.assertEqual(len(encoder.passage_inputs), 2)

    def test_stale_and_other_version_embeddings_do_not_suppress_pending(self):
        factory = FakeFactory(pending_rows(3))
        factory.stored[("e0", "e5", "document-v1")] = ("e0", "e5", "document-v1", "x" * 64)
        factory.stored[("e1", "e5", "other")] = ("e1", "e5", "other", "1" * 64)
        factory.stored[("e2", "e5", "document-v1")] = ("e2", "e5", "document-v1", "2" * 64)
        result = self.run_build(factory, FakeEncoder(factory))
        self.assertEqual((result.selected, result.embedded, result.unchanged), (2, 2, 1))

    def test_failure_keeps_first_batch_and_rerun_finishes_only_remaining(self):
        factory = FakeFactory(pending_rows(3))
        with self.assertRaises(EmbeddingBuildError) as raised:
            self.run_build(factory, FakeEncoder(factory, fail_batch=2))
        self.assertEqual((raised.exception.summary.embedded, raised.exception.summary.failed), (2, 1))
        self.assertEqual(factory.committed_batches, 1)
        result = self.run_build(factory, FakeEncoder(factory))
        self.assertEqual((result.selected, result.embedded, result.unchanged), (1, 1, 2))

    def test_write_failure_rolls_back_batch(self):
        factory = FakeFactory(pending_rows(2))
        factory.fail_write = True
        with self.assertRaises(EmbeddingBuildError) as raised:
            self.run_build(factory, FakeEncoder(factory))
        self.assertEqual(raised.exception.summary.failed, 2)
        self.assertEqual(factory.stored, {})

    def test_bad_vector_count_nonfinite_zero_and_rank_fail_before_write(self):
        for vectors in ([[1, 2]], [[0, 0], [0, 0]], [[1, float('nan')], [1, 2]], [1, 2]):
            with self.subTest(vectors=vectors):
                factory = FakeFactory(pending_rows(2))
                with self.assertRaises(EmbeddingBuildError):
                    self.run_build(factory, FakeEncoder(factory, vectors=vectors))
                self.assertEqual(factory.stored, {})

    def test_dimension_change_preserves_only_previous_batch(self):
        factory = FakeFactory(pending_rows(3))
        encoder = FakeEncoder(factory)
        original = encoder.embed_passages

        def changing_dimension(texts):
            vectors = original(texts)
            return vectors if len(encoder.passage_inputs) == 1 else np.ones((len(texts), 3))

        encoder.embed_passages = changing_dimension
        with self.assertRaises(EmbeddingBuildError) as raised:
            self.run_build(factory, encoder)
        self.assertEqual((raised.exception.summary.embedded, raised.exception.summary.failed), (2, 1))
        self.assertEqual(len(factory.stored), 2)

    def test_company_filter_and_empty_selection_do_not_embed_other_companies(self):
        factory = FakeFactory(pending_rows(2))
        factory.rows[1]['corp_code'] = '00164779'
        encoder = FakeEncoder(factory)
        summary = build_embeddings(factory, encoder, model='e5', version='v1',
                                   corp_codes=['00164779'], batch_size=2)
        self.assertEqual((summary.selected, summary.embedded), (1, 1))
        self.assertEqual(set(factory.stored), {('e1', 'e5', 'v1')})
        empty = build_embeddings(factory, None, model='e5', version='v1', corp_codes=[])
        self.assertEqual((empty.selected, empty.embedded), (0, 0))

    def test_source_type_filter_selects_only_business_reports(self):
        rows = pending_rows(2)
        rows[0]["source_type"] = "DART_BUSINESS_REPORT"
        rows[1]["source_type"] = "NEWS"
        factory = FakeFactory(rows)
        summary = build_embeddings(
            factory, FakeEncoder(factory), model="e5", version="v1",
            corp_codes=["00126380"], source_types=["DART_BUSINESS_REPORT"], batch_size=2,
        )
        self.assertEqual((summary.selected, summary.embedded), (1, 1))
        self.assertEqual({row[0] for row in factory.stored.values()}, {"e0"})

    def test_company_and_source_type_filters_have_matching_count_and_pending_semantics(self):
        rows = pending_rows(3)
        rows[0].update(corp_code="00126380", source_type="DART_BUSINESS_REPORT")
        rows[1].update(corp_code="00126380", source_type="NEWS")
        rows[2].update(corp_code="00164779", source_type="DART_BUSINESS_REPORT")
        factory = FakeFactory(rows)
        summary = build_embeddings(
            factory, FakeEncoder(factory), model="e5", version="v1",
            corp_codes=["00126380"], source_types=["DART_BUSINESS_REPORT"], batch_size=1,
        )
        self.assertEqual((summary.selected, summary.embedded, summary.unchanged), (1, 1, 0))
        self.assertEqual(set(factory.stored), {("e0", "e5", "v1")})
        count_params = next(params for sql, params in factory.executed if "COUNT(*)" in sql)
        pending_params = next(params for sql, params in factory.executed if sql.startswith("SELECT e.evidence_id"))
        self.assertEqual(count_params, ["e5", "v1", ["00126380"], ["DART_BUSINESS_REPORT"]])
        self.assertEqual(pending_params[:4], count_params)

    def test_empty_source_type_selection_and_filtered_dry_run_do_not_embed(self):
        rows = pending_rows(2)
        rows[0]["source_type"] = "DART_BUSINESS_REPORT"
        rows[1]["source_type"] = "NEWS"
        empty_factory = FakeFactory(rows)
        empty = build_embeddings(
            empty_factory, None, model="e5", version="v1", corp_codes=None,
            source_types=[],
        )
        self.assertEqual((empty.selected, empty.embedded, empty.unchanged), (0, 0, 0))
        dry_factory = FakeFactory(rows)
        dry = build_embeddings(
            dry_factory, None, model="e5", version="v1", corp_codes=None,
            source_types=["DART_BUSINESS_REPORT"], dry_run=True,
        )
        self.assertEqual((dry.selected, dry.embedded), (1, 0))
        self.assertEqual(dry_factory.stored, {})

    def test_failure_resume_keeps_the_same_source_type_filter(self):
        rows = pending_rows(3)
        rows[0]["source_type"] = "DART_BUSINESS_REPORT"
        rows[1]["source_type"] = "NEWS"
        rows[2]["source_type"] = "DART_BUSINESS_REPORT"
        factory = FakeFactory(rows)
        with self.assertRaises(EmbeddingBuildError) as raised:
            build_embeddings(
                factory, FakeEncoder(factory, fail_batch=2), model="e5", version="v1",
                corp_codes=None, source_types=["DART_BUSINESS_REPORT"], batch_size=1,
            )
        self.assertEqual((raised.exception.summary.embedded, raised.exception.summary.failed), (1, 1))
        resumed = build_embeddings(
            factory, FakeEncoder(factory), model="e5", version="v1",
            corp_codes=None, source_types=["DART_BUSINESS_REPORT"], batch_size=1,
        )
        self.assertEqual((resumed.selected, resumed.embedded, resumed.unchanged), (1, 1, 1))
        self.assertEqual(set(factory.stored), {("e0", "e5", "v1"), ("e2", "e5", "v1")})

    def test_default_tuple_cursor_maps_all_evidence_fields(self):
        factory = FakeFactory(pending_rows(1))
        connection = FakeConnection(factory)
        connection.fetchall = lambda: [tuple(factory.rows[0].values())]
        row = EmbeddingBuildRepository(connection).pending('e5', 'v1', None)[0]
        self.assertEqual(row, factory.rows[0])

    def test_dry_run_counts_without_encoder_or_writes(self):
        factory = FakeFactory(pending_rows(3))
        summary = build_embeddings(factory, None, model="e5", version="document-v1", corp_codes=None, batch_size=2, dry_run=True)
        self.assertEqual((summary.selected, summary.embedded, summary.dimension), (3, 0, None))
        self.assertEqual(factory.stored, {})
        self.assertEqual(len(factory.executed), 1)

    def test_invalid_arguments_fail_before_db_access(self):
        for options in ({"batch_size": 0}, {"model": ""}, {"version": ""}):
            factory = FakeFactory([])
            args = dict(model="e5", version="v1", corp_codes=None, batch_size=2, dry_run=False)
            args.update(options)
            with self.assertRaises(ValueError):
                build_embeddings(factory, None, **args)
            self.assertEqual(factory.executed, [])

    def test_invalid_source_type_fails_before_db_access(self):
        factory = FakeFactory(pending_rows(1))
        with self.assertRaises(ValueError):
            build_embeddings(
                factory, None, model="e5", version="v1", corp_codes=None,
                source_types=["UNSUPPORTED"],
            )
        self.assertEqual(factory.executed, [])
