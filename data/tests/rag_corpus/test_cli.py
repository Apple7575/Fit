from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

DATA = Path(__file__).resolve().parents[2]
SCRIPTS = DATA / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_rag_corpus
import load_rag_corpus_staging
from pipeline.rag_corpus.load import BuildResult
from pipeline.rag_corpus.source import CompanySourceRows
from pipeline.rag_corpus.transform import profile_record
from pipeline.raw_sources.models import EvidenceBatch
from pipeline.raw_sources.business_report import BusinessReportSource
from pipeline.raw_sources.dart_archive import DartArchive
from pipeline.raw_sources.staging import stage_batch


FIRST = "00126380"
SECOND = "00164779"


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 1

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))

    def fetchall(self):
        return [(code,) for code in self.conn.company_codes]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, company_codes):
        self.company_codes = company_codes
        self.queries = []
        self.replacements = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return Cursor(self)


class ConnectionFactory:
    def __init__(self, company_codes):
        self.company_codes = company_codes
        self.connections = []

    def __call__(self):
        conn = Connection(self.company_codes)
        self.connections.append(conn)
        return Transaction(conn)


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.conn.committed = True
        else:
            self.conn.rolled_back = True
        return False


def rows(corp_code):
    return CompanySourceRows(
        profile={"corp_code": corp_code, "corp_name": "테스트기업", "dart_modify_date": "20260913"},
        metrics=[], texts=[], segments=[], activities=[])


def result(corp_code):
    return BuildResult(
        records=[],
        input_counts={"profile": 1, "metrics": 0, "texts": 0, "segments": 0, "activities": 0},
        excluded_counts={},
    )


class BuildRagCorpusCliTest(unittest.TestCase):
    def test_staging_loader_replaces_company_without_reading_xml(self):
        factory = ConnectionFactory([FIRST])
        with tempfile.TemporaryDirectory() as directory:
            staging_dir = Path(directory)
            stage_batch(
                staging_dir, FIRST, EvidenceBatch([], {"documents": 0}, {}),
                source_signature="archive-v1",
            )
            with patch.object(load_rag_corpus_staging, "replace_business_reports") as replace:
                summary = load_rag_corpus_staging.load_staging(
                    factory, staging_dir, corp_codes=[FIRST], dry_run=False,
                )

        self.assertEqual(summary["company_count"], 1)
        self.assertEqual(summary["record_count"], 0)
        replace.assert_called_once()

    # 이 테스트가 막는 결함: 전용 모드를 선언해도 DART archive를 전달할 수 없는 경우.
    def test_parse_args_accepts_business_report_only_with_dart_archive(self):
        args = build_rag_corpus.parse_args([
            "--business-report-only", "--dart-archive", "dart-reports.zip",
        ])

        self.assertTrue(args.business_report_only)
        self.assertEqual(args.dart_archive, Path("dart-reports.zip"))

    def test_parse_args_accepts_json_output_path(self):
        args = build_rag_corpus.parse_args(["--dry-run", "--output", "result.json"])

        self.assertEqual(args.output, Path("result.json"))

    def test_parse_args_accepts_parallel_workers_and_extract_dir(self):
        args = build_rag_corpus.parse_args([
            "--business-report-only", "--dart-archive", "reports.zip",
            "--workers", "4", "--extract-dir", "dart-cache", "--staging-dir", "rag-stage",
            "--chunking-profile", "adaptive-v1",
        ])

        self.assertEqual(args.workers, 4)
        self.assertEqual(args.extract_dir, Path("dart-cache"))
        self.assertEqual(args.staging_dir, Path("rag-stage"))
        self.assertEqual(args.chunking_profile, "adaptive-v1")

    # 이 테스트가 막는 결함: 전용 모드의 잘못된 옵션 조합이 DB 접속 뒤에 발견되는 경우.
    def test_main_rejects_business_report_only_without_archive_before_database_connection(self):
        with patch.object(build_rag_corpus, "connect") as connect, \
             patch.object(sys, "argv", ["build_rag_corpus.py", "--business-report-only"]), \
             redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit):
            build_rag_corpus.main()

        self.assertFalse(connect.called)

    # 이 테스트가 막는 결함: 전용 스키마에 없는 정본 테이블을 사업보고서 전용 모드가 읽는 경우.
    def test_business_report_only_uses_only_dart_records_without_loading_master_sources(self):
        factory = ConnectionFactory([FIRST])
        report = replace(
            profile_record({"corp_code": FIRST, "corp_name": "테스트기업", "dart_modify_date": "20260913"}),
            evidence_id="dart-1", source_identity="dart_business_report:00126380:2025:1",
            source_type="DART_BUSINESS_REPORT", metadata={"content_type": "TEXT"},
        )

        class Provider:
            def batch(self, corp_code):
                return EvidenceBatch([report], {"documents": 1}, {})

            def inventory(self):
                return {"documents": 1}

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=AssertionError("master loader called")):
            summary = build_rag_corpus.run(
                factory, [FIRST], dry_run=True, external_providers=[Provider()], business_report_only=True,
            )

        self.assertEqual(summary["record_count"], 1)
        self.assertEqual(summary["companies"][FIRST]["write_status"], "dry_run")
        self.assertEqual(factory.connections[1].queries, [])

    # 이 테스트가 막는 결함: 실제 전용 동기화가 사업보고서 외 근거까지 지우는 경우.
    def test_business_report_only_actual_sync_scopes_delete_to_dart_source_type(self):
        factory = ConnectionFactory([FIRST])
        report = replace(
            profile_record({"corp_code": FIRST, "corp_name": "테스트기업", "dart_modify_date": "20260913"}),
            evidence_id="dart-1", source_identity="dart_business_report:00126380:2025:1",
            source_type="DART_BUSINESS_REPORT", metadata={"content_type": "TEXT"},
        )

        class Provider:
            def batch(self, corp_code):
                return EvidenceBatch([report], {"documents": 1}, {})

            def inventory(self):
                return {"documents": 1}

        summary = build_rag_corpus.run(
            factory, [FIRST], dry_run=False, external_providers=[Provider()], business_report_only=True,
        )

        self.assertEqual(summary["companies"][FIRST]["write_status"], "replaced")
        _, delete_params = factory.connections[1].queries[-1]
        self.assertEqual(delete_params, (FIRST, "DART_BUSINESS_REPORT", ["dart-1"]))

    # 이 테스트가 막는 결함: 선택 기업의 사업보고서가 없을 때 기존 사업보고서 근거를 지우는 경우.
    def test_business_report_only_preserves_existing_records_when_no_source_documents_exist(self):
        factory = ConnectionFactory([FIRST])

        class Provider:
            def batch(self, corp_code):
                return EvidenceBatch([], {"documents": 0}, {})

            def inventory(self):
                return {"documents": 0}

        summary = build_rag_corpus.run(
            factory, [FIRST], dry_run=False, external_providers=[Provider()], business_report_only=True,
        )

        self.assertEqual(summary["companies"][FIRST]["write_status"], "skipped_due_to_source_failure")
        self.assertEqual(summary["failures"], [{
            "corp_code": FIRST, "provider": "Provider", "reason": "no_source_documents",
        }])
        self.assertEqual(factory.connections[1].queries, [])

    # 이 테스트가 막는 결함: XML 파싱 실패가 있어도 전용 동기화가 기존 근거를 교체하는 경우.
    def test_business_report_only_defers_load_when_source_has_failure(self):
        factory = ConnectionFactory([FIRST])

        class Provider:
            def batch(self, corp_code):
                return EvidenceBatch([], {"documents": 1}, {}, failures=({"reason": "xml_parse_error"},))

            def inventory(self):
                return {"documents": 1}

        summary = build_rag_corpus.run(
            factory, [FIRST], dry_run=False, external_providers=[Provider()], business_report_only=True,
        )

        self.assertEqual(summary["companies"][FIRST]["write_status"], "skipped_due_to_source_failure")
        self.assertEqual(factory.connections[1].queries, [])

    # 이 테스트가 막는 결함: CLI가 파싱한 전용 모드 플래그를 실행 경로에 전달하지 않는 경우.
    def test_main_forwards_business_report_only_flag_to_run(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            with zipfile.ZipFile(archive_path, "w") as archive_file:
                archive_file.writestr(
                    "dart_local/company_reports.csv",
                    "corp_name,corp_code,year,rcept_no,rcept_dt,file\n"
                    f"테스트기업,{FIRST},2024,20250318000001,20250318,missing.xml\n",
                )
            with patch.object(build_rag_corpus, "run", return_value={"failures": []}) as run, \
                 patch.object(sys, "argv", [
                     "build_rag_corpus.py", "--business-report-only", "--dart-archive", str(archive_path),
                 ]), \
                 redirect_stdout(io.StringIO()):
                exit_code = build_rag_corpus.main()

        self.assertEqual(exit_code, 0)
        self.assertTrue(run.call_args.kwargs["business_report_only"])
        self.assertEqual(run.call_args.args[1], [FIRST])

    def test_main_uses_staging_path_with_one_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            extract_dir = Path(directory) / "extracted"
            staging_dir = Path(directory) / "staging"
            extract_dir.mkdir()
            (extract_dir / ".complete").write_text("archive-signature", encoding="utf-8")
            with zipfile.ZipFile(archive_path, "w") as archive_file:
                archive_file.writestr(
                    "dart_local/company_reports.csv",
                    "corp_name,corp_code,year,rcept_no,rcept_dt,file\n"
                    f"테스트기업,{FIRST},2024,20250318000001,20250318,missing.xml\n",
                )
            with patch.object(build_rag_corpus, "extract_archive", return_value=extract_dir), \
                 patch.object(build_rag_corpus, "run_parallel_business_reports", return_value={"failures": []}) as parallel, \
                 patch.object(sys, "argv", [
                     "build_rag_corpus.py", "--dry-run", "--business-report-only",
                     "--dart-archive", str(archive_path), "--workers", "1",
                     "--staging-dir", str(staging_dir),
                 ]), redirect_stdout(io.StringIO()):
                exit_code = build_rag_corpus.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(parallel.call_args.kwargs["staging_dir"], staging_dir)

    # 이 테스트가 막는 결함: 플래그 없는 기존 모드에서 정본 조회·외부 원천의 처리 순서가 바뀌는 경우.
    def test_default_mode_keeps_loading_master_sources_before_external_provider(self):
        factory = ConnectionFactory([FIRST])
        events = []

        class Provider:
            def batch(self, corp_code):
                events.append("provider")
                return EvidenceBatch([], {}, {})

            def inventory(self):
                return {}

        def load_master(conn, corp_code):
            events.append("master")
            return rows(corp_code)

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=load_master):
            build_rag_corpus.run(factory, [FIRST], dry_run=True, external_providers=[Provider()])

        self.assertEqual(events, ["master", "provider"])

    def test_run_merges_selected_external_provider_records_into_each_company(self):
        factory = ConnectionFactory([FIRST])
        provider_record = object()

        class Provider:
            def batch(self, corp_code):
                self.corp_code = corp_code
                return EvidenceBatch([provider_record], {}, {})

            def inventory(self):
                return {"documents": 1}

        provider = Provider()
        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source, *, external_records: result(source.profile["corp_code"])) as build:
            summary = build_rag_corpus.run(factory, [FIRST], dry_run=True, external_providers=[provider])

        self.assertEqual(provider.corp_code, FIRST)
        self.assertEqual(build.call_args.kwargs["external_records"], [provider_record])
        self.assertEqual(summary["external_sources"], [{"provider": "Provider", "inventory": {"documents": 1}}])

    def test_run_does_not_replace_company_when_external_source_has_partial_failure(self):
        factory = ConnectionFactory([FIRST])

        class Provider:
            def batch(self, corp_code):
                return EvidenceBatch([], {}, {}, failures=({"rcept_no": "20250318000001", "reason": "xml_parse_error"},))

            def inventory(self):
                return {"documents": 1}

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source, *, external_records: result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company") as replace:
            summary = build_rag_corpus.run(factory, [FIRST], dry_run=False, external_providers=[Provider()])

        self.assertFalse(replace.called)
        self.assertEqual(summary["companies"][FIRST]["write_status"], "skipped_due_to_source_failure")
        self.assertEqual(summary["failures"][0]["corp_code"], FIRST)

    def test_run_preserves_existing_corpus_when_manifest_xml_is_missing(self):
        factory = ConnectionFactory([FIRST])
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "dart.zip"
            output = io.StringIO(newline="")
            writer = csv.DictWriter(
                output,
                fieldnames=["corp_name", "corp_code", "year", "rcept_no", "rcept_dt", "report_nm", "file"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow({
                "corp_name": "테스트기업", "corp_code": FIRST, "year": 2024,
                "rcept_no": "20250318000001", "rcept_dt": "20250318", "report_nm": "사업보고서",
                "file": "document_20250318000001.xml",
            })
            with zipfile.ZipFile(archive_path, "w") as archive_file:
                archive_file.writestr("dart_local/company_reports.csv", output.getvalue())
            with DartArchive(archive_path) as archive:
                provider = BusinessReportSource(archive)
                with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
                     patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source, *, external_records: result(source.profile["corp_code"])), \
                     patch.object(build_rag_corpus, "replace_company") as replace:
                    summary = build_rag_corpus.run(factory, [FIRST], dry_run=False, external_providers=[provider])

        self.assertFalse(replace.called)
        self.assertEqual(summary["companies"][FIRST]["write_status"], "skipped_due_to_source_failure")
        self.assertEqual(summary["failures"], [{
            "corp_code": FIRST, "rcept_no": "20250318000001",
            "document_file": "document_20250318000001.xml", "reason": "manifest_missing_xml",
            "provider": "BusinessReportSource",
        }])

    def test_run_aggregates_business_report_counts_and_float32_capacity_per_company_and_total(self):
        factory = ConnectionFactory([FIRST, SECOND])
        base = profile_record({"corp_code": FIRST, "corp_name": "테스트기업", "dart_modify_date": "20260913"})

        class Provider:
            def batch(self, corp_code):
                records = [
                    replace(base, corp_code=corp_code, evidence_id=f"{corp_code}-{kind}",
                            source_identity=f"dart:{corp_code}:{kind}", source_type="DART_BUSINESS_REPORT",
                            metadata={"content_type": kind})
                    for kind in ("TEXT", "TABLE")
                ]
                return EvidenceBatch(
                    records, {"documents": 1, "sections": 2, "paragraphs": 3, "tables": 1},
                    {"table_too_large": 1},
                )

            def inventory(self):
                return {"documents": 2}

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)):
            summary = build_rag_corpus.run(
                factory, None, dry_run=True, external_providers=[Provider()], embedding_dimension=512,
            )

        self.assertEqual(summary["company_count"], 2)
        self.assertEqual(summary["record_count"], 6)
        self.assertEqual(summary["input_counts"], {
            "activities": 0, "documents": 2, "metrics": 0, "paragraphs": 6,
            "profile": 2, "sections": 4, "segments": 0, "tables": 2, "texts": 0,
            "external:DART_BUSINESS_REPORT": 4,
            "business_report_text_chunks": 2, "business_report_table_chunks": 2,
        })
        self.assertEqual(summary["excluded_counts"], {"table_too_large": 2})
        self.assertEqual(summary["estimated_embedding_bytes"], 6 * 512 * 4)
        self.assertEqual(summary["companies"][FIRST]["estimated_embedding_bytes"], 3 * 512 * 4)
        self.assertEqual(summary["companies"][FIRST]["external_input_counts"], {
            "business_report_text_chunks": 1, "business_report_table_chunks": 1,
            "documents": 1, "paragraphs": 3, "sections": 2, "tables": 1,
        })
        self.assertEqual(summary["companies"][SECOND]["external_excluded_counts"], {"table_too_large": 1})

    # 이 테스트가 막는 결함: 전체 실행 시간만 출력하고 기업별 처리 시간·기업 수를 누락하는 경우.
    def test_run_measures_each_company_through_its_database_context(self):
        factory = ConnectionFactory([FIRST, SECOND])

        class DeterministicBuildSummary(build_rag_corpus.BuildSummary):
            def __init__(self):
                super().__init__(started_at=build_rag_corpus.time.monotonic())

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "BuildSummary", DeterministicBuildSummary), \
             patch.object(build_rag_corpus.time, "monotonic", side_effect=[100.0, 101.0, 104.0, 110.0, 117.0, 120.0]):
            summary = build_rag_corpus.run(factory, None, dry_run=True)

        first = summary["companies"][FIRST]
        second = summary["companies"][SECOND]
        self.assertEqual((first["company_count"], second["company_count"]), (1, 1))
        self.assertEqual((first["elapsed_ms"], second["elapsed_ms"]), (3000, 7000))
        self.assertIsInstance(first["elapsed_ms"], int)
        self.assertEqual(summary["elapsed_ms"], 20000)

    def test_embedding_dimension_must_be_positive_before_opening_the_database(self):
        factory = ConnectionFactory([FIRST])

        self.assertEqual(build_rag_corpus.parse_args([]).embedding_dimension, 1024)

        with self.assertRaisesRegex(ValueError, "embedding_dimension"):
            build_rag_corpus.run(factory, None, dry_run=True, embedding_dimension=0)

        self.assertEqual(factory.connections, [])
        for dimension in ("0", "-1"):
            with self.subTest(dimension=dimension), self.assertRaises(SystemExit):
                with redirect_stderr(io.StringIO()):
                    build_rag_corpus.parse_args(["--embedding-dimension", dimension])

    # 이 테스트가 막는 결함: 전체 재구축에서 DB 반환 순서대로 처리해 결과가 비결정적이 되는 경우.
    def test_run_selects_every_company_in_sorted_order(self):
        factory = ConnectionFactory([SECOND, FIRST])
        built = []

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records",
                          side_effect=lambda source: built.append(source.profile["corp_code"]) or result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=lambda conn, code, _: conn.replacements.append(code)):
            summary = build_rag_corpus.run(factory, None, dry_run=False)

        self.assertEqual(built, [FIRST, SECOND])
        self.assertEqual(summary["company_count"], 2)
        self.assertEqual([conn.replacements for conn in factory.connections[1:]], [[FIRST], [SECOND]])

    # 이 테스트가 막는 결함: 반복된 옵션이 같은 기업을 두 번 지우고 다시 넣는 경우.
    def test_run_deduplicates_targeted_company_codes_preserving_first_request_order(self):
        factory = ConnectionFactory([FIRST, SECOND])
        built = []

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records",
                          side_effect=lambda source: built.append(source.profile["corp_code"]) or result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=lambda conn, code, _: conn.replacements.append(code)):
            build_rag_corpus.run(factory, [SECOND, FIRST, SECOND], dry_run=False)

        self.assertEqual(built, [SECOND, FIRST])
        self.assertEqual([conn.replacements for conn in factory.connections[1:]], [[SECOND], [FIRST]])

    # 이 테스트가 막는 결함: 존재하지 않는 코드를 첫 기업 교체 뒤에 발견해 이미 DB를 바꾸는 경우.
    def test_run_rejects_unknown_company_before_any_mutation(self):
        factory = ConnectionFactory([FIRST])

        with patch.object(build_rag_corpus, "replace_company") as replace:
            with self.assertRaisesRegex(ValueError, "기업을 찾을 수 없습니다: 99999999"):
                build_rag_corpus.run(factory, [FIRST, "99999999"], dry_run=False)

        self.assertFalse(replace.called)
        self.assertEqual(len(factory.connections), 1)

    # 이 테스트가 막는 결함: dry run이 기존 코퍼스를 삭제하거나 새 행을 삽입하는 경우.
    def test_run_dry_run_does_not_replace_any_company(self):
        factory = ConnectionFactory([FIRST])

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source: result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company") as replace:
            summary = build_rag_corpus.run(factory, [FIRST], dry_run=True)

        self.assertEqual(summary["company_count"], 1)
        self.assertFalse(replace.called)
        self.assertTrue(factory.connections[1].committed)

    # 이 테스트가 막는 결함: 기업 교체 중 오류가 나도 예전 코퍼스가 삭제된 채로 커밋되는 경우.
    def test_main_returns_one_and_rolls_back_the_failing_company_transaction(self):
        factory = ConnectionFactory([FIRST])
        output = io.StringIO()

        with patch.object(build_rag_corpus, "connect", factory), \
             patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source: result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=RuntimeError("insert failed")), \
             patch.object(sys, "argv", ["build_rag_corpus.py", "--corp-code", FIRST]), \
             redirect_stdout(output):
            exit_code = build_rag_corpus.main()

        self.assertEqual(exit_code, 1)
        self.assertTrue(factory.connections[1].rolled_back)
        self.assertFalse(factory.connections[1].committed)
        self.assertEqual(json.loads(output.getvalue()), {"status": "failed", "error": "insert failed"})


if __name__ == "__main__":
    unittest.main()
