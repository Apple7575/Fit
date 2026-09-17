from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import build_rag_embeddings as cli
from tests.rag_corpus.test_embedding_build import FakeFactory, FakeEncoder, pending_rows


class EmbeddingCliTests(unittest.TestCase):
    def invoke(self, args, factory, known=None):
        output = StringIO()
        with patch.object(cli, "connect", factory), patch.object(cli, "resolve_company_codes", side_effect=known or (lambda factory, codes: codes)), redirect_stdout(output):
            code = cli.main(args)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return code, json.loads(output.getvalue())

    def test_dry_run_never_constructs_encoder_and_reports_default_dimension(self):
        factory = FakeFactory(pending_rows(3))
        with patch.object(cli, "FastEmbedEncoder", side_effect=AssertionError("must not load")):
            code, payload = self.invoke(["--dry-run", "--corp-code", "00126380"], factory)
        self.assertEqual(code, 0)
        self.assertEqual((payload['status'], payload['selected'], payload['embedded'], payload['dimension']), ('success', 3, 0, 1024))
        self.assertEqual(factory.stored, {})

    def test_default_model_is_qwen3_embedding(self):
        factory = FakeFactory([])
        code, payload = self.invoke(["--dry-run"], factory)

        self.assertEqual(code, 0)
        self.assertEqual(cli.parse_args([]).batch_size, 32)
        count_params = next(params for sql, params in factory.executed if "COUNT(*)" in sql)
        self.assertEqual(count_params[:2], ["Qwen/Qwen3-Embedding-0.6B", "document-v1"])

    def test_qwen3_real_build_requires_remote_vllm_before_database_access(self):
        factory = FakeFactory(pending_rows(1))
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(cli, "FastEmbedEncoder") as local_encoder:
            code, payload = self.invoke([], factory)

        self.assertEqual((code, payload["status"]), (1, "failed"))
        local_encoder.assert_not_called()
        self.assertEqual(factory.executed, [])

    def test_real_path_uses_selected_options_and_writes(self):
        factory = FakeFactory(pending_rows(3))
        encoder = FakeEncoder(factory)
        with patch.object(cli, "FastEmbedEncoder", return_value=encoder):
            code, payload = self.invoke(["--model", "custom", "--version", "v2", "--batch-size", "2"], factory)
        self.assertEqual((code, payload['embedded']), (0, 3))
        self.assertEqual({key[1:] for key in factory.stored}, {('custom', 'v2')})

    def test_explicit_cuda_device_is_forwarded_without_cpu_fallback(self):
        factory = FakeFactory(pending_rows(1))
        encoder = FakeEncoder(factory)
        with patch.object(cli, "FastEmbedEncoder", return_value=encoder) as constructor:
            code, payload = self.invoke(["--model", "custom", "--device", "cuda"], factory)

        self.assertEqual((code, payload["embedded"]), (0, 1))
        constructor.assert_called_once_with("custom", device="cuda")

    def test_remote_url_uses_remote_encoder_without_loading_local_model(self):
        factory = FakeFactory(pending_rows(1))
        encoder = FakeEncoder(factory)
        with patch.object(cli, "FastEmbedEncoder", side_effect=AssertionError("must not load")), \
             patch.object(cli, "RemoteEmbeddingEncoder", return_value=encoder) as constructor, \
             patch.dict("os.environ", {
                 "EMBEDDING_API_KEY": "key",
                 "EMBEDDING_SERVED_MODEL": "main-embedding",
             }):
            code, payload = self.invoke([
                "--model", "custom", "--remote-url", "http://gpu:8001",
            ], factory)

        self.assertEqual((code, payload["embedded"]), (0, 1))
        constructor.assert_called_once_with(
            "custom", base_url="http://gpu:8001", api_key="key",
            served_model_name="main-embedding",
        )

    def test_remote_url_requires_key_before_database_access(self):
        factory = FakeFactory(pending_rows(1))
        with patch.dict("os.environ", {}, clear=True):
            code, payload = self.invoke(["--remote-url", "http://gpu:8001"], factory)

        self.assertEqual((code, payload["status"]), (1, "failed"))
        self.assertEqual(factory.executed, [])

    def test_repeated_source_type_filters_and_deduplicates_in_input_order(self):
        rows = pending_rows(3)
        rows[0]["source_type"] = "DART_BUSINESS_REPORT"
        rows[1]["source_type"] = "NEWS"
        rows[2]["source_type"] = "DART_BUSINESS_REPORT"
        factory = FakeFactory(rows)
        encoder = FakeEncoder(factory)
        with patch.object(cli, "FastEmbedEncoder", return_value=encoder):
            code, payload = self.invoke([
                "--model", "e5",
                "--source-type", "DART_BUSINESS_REPORT",
                "--source-type", "NEWS",
                "--source-type", "DART_BUSINESS_REPORT",
            ], factory)
        self.assertEqual((code, payload["selected"], payload["embedded"]), (0, 3, 3))
        count_params = next(params for sql, params in factory.executed if "COUNT(*)" in sql)
        self.assertEqual(count_params, ["e5", "document-v1", ["DART_BUSINESS_REPORT", "NEWS"]])

    def test_unknown_company_rejected_before_model_or_mutation(self):
        factory = FakeFactory(pending_rows(1))
        with patch.object(cli, "FastEmbedEncoder", side_effect=AssertionError("must not load")):
            code, payload = self.invoke(["--corp-code", "99999999"], factory, known=ValueError("unknown"))
        self.assertEqual((code, payload['status']), (1, 'failed'))
        self.assertEqual(factory.stored, {})

    def test_invalid_source_type_is_rejected_before_model_construction(self):
        factory = FakeFactory(pending_rows(1))
        with patch.object(cli, "FastEmbedEncoder", return_value=FakeEncoder(factory)) as constructor:
            code, payload = self.invoke(["--source-type", "UNSUPPORTED"], factory)
        self.assertEqual((code, payload["status"]), (1, "failed"))
        constructor.assert_not_called()
        self.assertEqual(factory.executed, [])

    def test_failure_json_never_exposes_db_or_model_exception_details(self):
        factory = FakeFactory(pending_rows(1))
        with patch.object(cli, "FastEmbedEncoder", side_effect=RuntimeError("postgresql://user:secret@host/db")):
            code, payload = self.invoke([], factory)
        self.assertEqual((code, payload['status']), (1, 'failed'))
        self.assertNotIn('secret', json.dumps(payload))

    def test_argument_errors_are_json_and_exit_one(self):
        for args in (
            ["--batch-size", "0"], ["--batch-size", "bad"], ["--unknown"],
            ["--model", ""], ["--device", "tpu"],
        ):
            with self.subTest(args=args):
                code, payload = self.invoke(args, FakeFactory([]))
                self.assertEqual((code, payload['status']), (1, 'failed'))

    def test_partial_failure_reports_committed_and_failed_batch_counts(self):
        factory = FakeFactory(pending_rows(3))
        with patch.object(cli, 'FastEmbedEncoder', return_value=FakeEncoder(factory, fail_batch=2)):
            code, payload = self.invoke(['--model', 'e5', '--batch-size', '2'], factory)
        self.assertEqual((code, payload['selected'], payload['embedded'], payload['failed']), (1, 3, 2, 1))
        self.assertEqual(factory.committed_batches, 1)

    def test_unknown_model_dry_run_reports_unknown_dimension_without_loading(self):
        with patch.object(cli, 'FastEmbedEncoder', side_effect=AssertionError('must not load')):
            code, payload = self.invoke(['--dry-run', '--model', 'custom'], FakeFactory([]))
        self.assertEqual(code, 0)
        self.assertIsNone(payload['dimension'])

    def test_model_loading_and_inference_suppress_prebound_dependency_logs(self):
        probe = textwrap.dedent('''
            import os
            import sys
            from unittest.mock import patch
            from loguru import logger
            from scripts import build_rag_embeddings as cli
            from pipeline.rag_corpus.embedding_build import EmbeddingBuildSummary

            stage, outcome, token = sys.argv[1:]
            logger.remove()
            logger.add(sys.stderr, format="{message}")
            url = "https://example.invalid/model?token=" + token

            def dependency_output():
                print(url)
                print(url, file=sys.stderr)
                logger.error(url)
                os.write(2, url.encode())
                if outcome == "failure":
                    raise OSError(url)

            def load_model(*args, **kwargs):
                if stage == "loading":
                    dependency_output()
                return object()

            def build(*args, **kwargs):
                if stage == "inference":
                    dependency_output()
                return EmbeddingBuildSummary()

            with patch.object(cli, "resolve_company_codes", return_value=[]), \\
                 patch.object(cli, "FastEmbedEncoder", side_effect=load_model), \\
                 patch.object(cli, "build_embeddings", side_effect=build):
                raise SystemExit(cli.main(["--model", "intfloat/multilingual-e5-large"]))
        ''')
        for stage in ('loading', 'inference'):
            for outcome in ('success', 'failure'):
                with self.subTest(stage=stage, outcome=outcome):
                    token = uuid4().hex
                    result = subprocess.run(
                        [sys.executable, '-c', probe, stage, outcome, token],
                        cwd=Path(__file__).resolve().parents[2],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(result.returncode, 1 if outcome == 'failure' else 0)
                    self.assertEqual(len(result.stdout.splitlines()), 1)
                    self.assertEqual(json.loads(result.stdout)['status'], 'failed' if outcome == 'failure' else 'success')
                    self.assertNotIn(token, result.stdout)
                    self.assertNotIn(token, result.stderr)
                    self.assertEqual(result.stderr, '')
