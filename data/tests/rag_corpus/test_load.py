from dataclasses import replace
from datetime import datetime, timezone
import unittest

from pipeline.rag_corpus.load import (
    build_business_report_records,
    build_company_records,
    replace_business_reports,
    replace_company,
)
from pipeline.rag_corpus.models import EvidenceRecord
from pipeline.rag_corpus.source import CompanySourceRows


CORP_CODE = "00126380"


def record(corp_code=CORP_CODE, source_identity="company:00126380", *, evidence_id="company-1",
           content_hash="0" * 64, source_type="COMPANY_PROFILE"):
    return EvidenceRecord(
        evidence_id=evidence_id, corp_code=corp_code, source_type=source_type,
        source_identity=source_identity, title="삼성전자 기업 기본 정보", content="본문",
        reference_period=None, published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_url=None, quality="PRIMARY", metadata={}, content_hash=content_hash,
        source_updated_at=None,
    )


class RecordingCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = -1

    def execute(self, query, params):
        self.conn.executed.append((query, params))
        normalized = " ".join(query.lower().split())
        if normalized.startswith("delete"):
            self.conn.deleted_company = params[0]
        elif normalized.startswith("insert"):
            self.conn.inserted_companies.append(params[1])
            existing = self.conn.stored_evidence.get(params[0])
            same_company = not existing or existing["corp_code"] == params[1]
            same_source_type = not existing or existing.get("source_type", params[2]) == params[2]
            guarded_company = "rag_evidence.corp_code = excluded.corp_code" in normalized
            guarded_source_type = "rag_evidence.source_type = excluded.source_type" in normalized
            if existing and guarded_company and (
                not same_company or (guarded_source_type and not same_source_type)
            ):
                self.rowcount = 0
            else:
                self.conn.stored_evidence[params[0]] = {
                    "corp_code": existing["corp_code"] if existing else params[1],
                    "source_type": existing.get("source_type", params[2]) if existing else params[2],
                    "source_identity": params[3], "content": params[5],
                }
                self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self):
        self.deleted_company = None
        self.inserted_companies = []
        self.executed = []
        self.committed = False
        self.rolled_back = False
        self.stored_evidence = {}

    def cursor(self):
        return RecordingCursor(self)

    def commit(self):
        self.committed = True

    def __enter__(self):
        self.before = self.stored_evidence.copy()
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is not None:
            self.stored_evidence = self.before
            self.rolled_back = True
        else:
            self.commit()
        return False


class BuildCompanyRecordsTest(unittest.TestCase):
    # 이 테스트가 막는 결함: 사업보고서 전용 적재에 다른 source type 근거가 섞이는 경우.
    def test_business_report_only_rejects_non_business_report_source_type(self):
        with self.assertRaisesRegex(ValueError, "DART_BUSINESS_REPORT"):
            build_business_report_records(CORP_CODE, [record(source_type="NEWS")])

    # 이 테스트가 막는 결함: 다른 기업 사업보고서가 대상 기업 근거로 저장되는 경우.
    def test_business_report_only_rejects_cross_company_record(self):
        report = record("00164779", "dart_business_report:00164779:2025:1", source_type="DART_BUSINESS_REPORT")

        with self.assertRaisesRegex(ValueError, "다른 기업"):
            build_business_report_records(CORP_CODE, [report])

    # 이 테스트가 막는 결함: 내용 없는 사업보고서가 기존 유효 근거를 지우는 경우.
    def test_business_report_only_rejects_blank_content(self):
        report = replace(
            record(source_identity="dart_business_report:00126380:2025:1", source_type="DART_BUSINESS_REPORT"),
            content=" ",
        )

        with self.assertRaisesRegex(ValueError, "빈 내용"):
            build_business_report_records(CORP_CODE, [report])

    # 이 테스트가 막는 결함: 같은 원문 좌표가 입력 순서에 따라 중복 저장되는 경우.
    def test_business_report_only_deduplicates_identical_source_identity(self):
        report = record(source_identity="dart_business_report:00126380:2025:1", source_type="DART_BUSINESS_REPORT")

        built = build_business_report_records(CORP_CODE, [replace(report, evidence_id="second"), report])

        self.assertEqual([item.evidence_id for item in built.records], ["company-1"])
        self.assertEqual(built.input_counts, {"external:DART_BUSINESS_REPORT": 2})
        self.assertEqual(built.excluded_counts, {"duplicate_source_identity": 1})

    # 이 테스트가 막는 결함: 같은 원문 좌표의 서로 다른 내용 중 하나를 임의로 저장하는 경우.
    def test_business_report_only_rejects_conflicting_source_identity(self):
        report = record(source_identity="dart_business_report:00126380:2025:1", source_type="DART_BUSINESS_REPORT")

        with self.assertRaisesRegex(ValueError, "source_identity.*content_hash"):
            build_business_report_records(CORP_CODE, [report, replace(report, content_hash="1" * 64)])

    def test_adds_same_company_external_evidence_and_rejects_cross_company_input(self):
        rows = CompanySourceRows(
            profile={"corp_code": CORP_CODE, "corp_name": "삼성전자", "dart_modify_date": "20260913"},
            metrics=[], texts=[], segments=[], activities=[],
        )
        external = record(
            source_identity="dart_business_report:00126380:20250318000001:1:text:0",
            evidence_id="dart-business-report-1",
            source_type="DART_BUSINESS_REPORT",
        )

        result = build_company_records(rows, external_records=[external])

        self.assertEqual(result.input_counts["external:DART_BUSINESS_REPORT"], 1)
        self.assertIn(external, result.records)
        with self.assertRaisesRegex(ValueError, "다른 기업"):
            build_company_records(rows, external_records=[record("00164779", "dart:other")])

    def test_builds_sorted_records_and_counts_generated_rejected_and_blank_inputs(self):
        rows = CompanySourceRows(
            profile={"corp_code": CORP_CODE, "corp_name": "삼성전자", "dart_modify_date": "20260913"},
            metrics=[
                {"corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
                 "metric_code": "revenue", "metric_name": "매출액", "metric_value": "1",
                 "unit": "KRW", "verdict": "verified", "rcept_no": None},
                {"corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
                 "metric_code": "rd_expense", "metric_name": "R&D 비용", "metric_value": "1",
                 "unit": "KRW", "verdict": "rejected", "rcept_no": None},
            ],
            texts=[
                {"corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
                 "attr_key": "main_product", "seq": 0, "value_text": "메모리", "generated_at": None},
                {"corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
                 "attr_key": "main_product", "seq": 1, "value_text": "생성물", "generated_at": "2026-01-01"},
                {"corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
                 "attr_key": "main_product", "seq": 2, "value_text": " ", "generated_at": None},
            ],
            segments=[], activities=[],
        )

        result = build_company_records(rows)

        self.assertEqual(result.input_counts, {"profile": 1, "metrics": 2, "texts": 3, "segments": 0, "activities": 0})
        self.assertEqual(result.excluded_counts, {"generated_text": 1, "metric_rejected": 1, "blank_content": 1})
        self.assertEqual([item.source_identity for item in result.records], [
            "company:00126380", "company_metric:00126380:2025:revenue", "company_text:00126380:2025:main_product",
        ])

    def test_keeps_one_of_identical_activity_records_and_counts_duplicate_source_identity(self):
        activity = {
            "corp_code": CORP_CODE, "corp_name": "삼성전자", "fiscal_year": 2025,
            "activity_type": "facility", "field_name": "반도체", "purpose": "증설",
            "amount": "10", "counterparty": "협력사", "rcept_no": "20260310002820",
        }
        rows = CompanySourceRows(
            profile=None, metrics=[], texts=[], segments=[],
            activities=[{**activity, "id": 1}, {**activity, "id": 2}],
        )

        result = build_company_records(rows)

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.excluded_counts, {"duplicate_source_identity": 1})

    def test_rejects_same_activity_identity_with_different_content_hash(self):
        activity = {
            "corp_code": CORP_CODE, "fiscal_year": 2025, "activity_type": "facility",
            "field_name": "반도체", "purpose": "증설", "amount": "10",
            "counterparty": "협력사", "rcept_no": "20260310002820",
        }
        rows = CompanySourceRows(
            profile=None, metrics=[], texts=[], segments=[], activities=[
                {**activity, "corp_name": "삼성전자"},
                {**activity, "corp_name": "삼성전자전자"},
            ],
        )

        with self.assertRaisesRegex(ValueError, "source_identity.*content_hash"):
            build_company_records(rows)


class ReplaceCompanyTest(unittest.TestCase):
    def test_cross_company_evidence_id_collision_rolls_back_before_obsolete_rows_are_deleted(self):
        conn = FakeConnection()
        conn.stored_evidence = {
            "company-1": {"corp_code": "00164779", "source_identity": "company:00164779", "content": "다른 기업"},
            "old-a": {"corp_code": CORP_CODE, "source_identity": "company:00126380:old", "content": "기존 근거"},
        }
        original = conn.stored_evidence.copy()
        new_record = replace(record(), evidence_id="new-a", source_identity="company:00126380:new")

        with self.assertRaisesRegex(ValueError, "다른 기업.*evidence_id"):
            with conn:
                replace_company(conn, CORP_CODE, [new_record, record()])

        self.assertEqual(conn.stored_evidence, original)
        self.assertTrue(conn.rolled_back)
        self.assertIsNone(conn.deleted_company)

    def test_upserts_same_company_records_then_deletes_only_missing_evidence(self):
        conn = FakeConnection()
        conn.stored_evidence = {
            "old-a": {"corp_code": CORP_CODE, "source_identity": "company:00126380:old", "content": "기존 근거"},
        }

        replace_company(conn, CORP_CODE, [record()])

        queries = [" ".join(sql.split()) for sql, _ in conn.executed]
        self.assertIn("ON CONFLICT (evidence_id) DO UPDATE", queries[0])
        self.assertIn("WHERE rag_evidence.corp_code = EXCLUDED.corp_code", queries[0])
        self.assertIn("evidence_id <> ALL", queries[-1])
        self.assertEqual(conn.executed[-1][1], (CORP_CODE, ["company-1"]))
    def test_delete_and_insert_use_the_same_company(self):
        conn = FakeConnection()

        inserted = replace_company(conn, CORP_CODE, [record()])

        self.assertEqual(inserted, 1)
        self.assertEqual(conn.deleted_company, CORP_CODE)
        self.assertEqual(conn.inserted_companies, [CORP_CODE])
        self.assertFalse(conn.committed)
        self.assertEqual(conn.executed[-1][1], (CORP_CODE, ["company-1"]))

    def test_rejects_cross_company_records_before_delete(self):
        conn = FakeConnection()

        with self.assertRaisesRegex(ValueError, "다른 기업"):
            replace_company(conn, CORP_CODE, [record("00164779", "company:00164779")])

        self.assertFalse(conn.executed)

    def test_rejects_conflicting_source_identity_before_delete(self):
        conn = FakeConnection()

        with self.assertRaisesRegex(ValueError, "source_identity.*content_hash"):
            replace_company(conn, CORP_CODE, [
                record(evidence_id="company-1", content_hash="0" * 64),
                record(evidence_id="company-2", content_hash="1" * 64),
            ])

        self.assertFalse(conn.executed)


class ReplaceBusinessReportsTest(unittest.TestCase):
    # 이 테스트가 막는 결함: 사업보고서 동기화가 COMPANY·NEWS 근거까지 삭제하는 경우.
    def test_replaces_only_business_reports_for_the_selected_company(self):
        conn = FakeConnection()
        report = record(
            source_identity="dart_business_report:00126380:2025:1",
            evidence_id="dart-report-1",
            source_type="DART_BUSINESS_REPORT",
        )

        replaced = replace_business_reports(conn, CORP_CODE, [report])

        self.assertEqual(replaced, 1)
        delete_sql, delete_params = conn.executed[-1]
        self.assertIn("source_type = %s", " ".join(delete_sql.split()))
        self.assertEqual(delete_params, (CORP_CODE, "DART_BUSINESS_REPORT", ["dart-report-1"]))

    # 이 테스트가 막는 결함: 같은 기업의 NEWS/COMPANY evidence_id를 사업보고서가 덮어쓰는 경우.
    def test_rejects_same_company_different_source_type_evidence_id_collision(self):
        conn = FakeConnection()
        report = record(
            source_identity="dart_business_report:00126380:2025:1",
            evidence_id="shared-id",
            source_type="DART_BUSINESS_REPORT",
        )
        conn.stored_evidence = {
            "shared-id": {
                "corp_code": CORP_CODE,
                "source_type": "NEWS",
                "source_identity": "news:00126380:existing",
                "content": "기존 뉴스",
            },
        }

        with self.assertRaisesRegex(ValueError, "기업 또는 source type 충돌"):
            replace_business_reports(conn, CORP_CODE, [report])

        self.assertEqual(conn.stored_evidence["shared-id"]["source_type"], "NEWS")
        self.assertEqual(len(conn.executed), 1)


if __name__ == "__main__":
    unittest.main()
