from datetime import datetime, timezone
from decimal import Decimal
import unittest

from pipeline.rag_corpus.models import EvidenceRecord
from pipeline.rag_corpus.transform import (
    activity_record,
    content_hash,
    metric_record,
    profile_record,
    segment_records,
    stable_evidence_id,
    text_records,
)


class RagCorpusTransformTest(unittest.TestCase):
    def test_stable_id_depends_only_on_source_identity(self):
        identity = "company_metric:00126380:2025:revenue"

        self.assertEqual(stable_evidence_id(identity), stable_evidence_id(identity))
        self.assertRegex(stable_evidence_id(identity), r"^company-metric-[0-9a-f]{32}$")

    def test_verified_metric_uses_receipt_date(self):
        record = metric_record({
            "corp_code": "00126380", "corp_name": "삼성전자",
            "fiscal_year": 2025, "metric_code": "revenue",
            "metric_name": "매출액", "unit": "KRW",
            "metric_value": Decimal("1000000"), "verdict": "verified",
            "rcept_no": "20260310002820", "source_updated_at": None,
        })

        self.assertEqual(record.quality, "VERIFIED")
        self.assertEqual(record.published_at, datetime(2026, 3, 10, tzinfo=timezone.utc))
        self.assertFalse(record.metadata["date_inferred"])
        self.assertEqual(record.content, "삼성전자의 2025년 매출액은 1000000 KRW입니다.")

    def test_metric_without_valid_receipt_uses_conservative_date(self):
        record = metric_record({
            "corp_code": "00126380", "corp_name": "삼성전자",
            "fiscal_year": 2025, "metric_code": "revenue",
            "metric_name": "매출액", "unit": "KRW",
            "metric_value": Decimal("1000000"), "verdict": "unverified",
            "rcept_no": "invalid", "source_updated_at": None,
        })

        self.assertEqual(record.quality, "UNVERIFIED")
        self.assertEqual(record.published_at, datetime(2026, 4, 1, tzinfo=timezone.utc))
        self.assertTrue(record.metadata["date_inferred"])

    def test_rejected_metric_is_excluded(self):
        record = metric_record({
            "corp_code": "00126380", "corp_name": "삼성전자",
            "fiscal_year": 2025, "metric_code": "rd_expense",
            "metric_name": "R&D 비용", "unit": "KRW",
            "metric_value": Decimal("1"), "verdict": "rejected",
            "rcept_no": None, "source_updated_at": None,
        })

        self.assertIsNone(record)

    def test_generated_company_text_is_excluded(self):
        records = text_records([{
            "corp_code": "00126380", "corp_name": "삼성전자",
            "fiscal_year": 2025, "attr_key": "main_business", "seq": 0,
            "value_text": "생성된 설명", "generated_at": "2026-09-09T00:00:00Z",
            "source_updated_at": None,
        }])

        self.assertEqual(records, [])

    def test_text_rows_are_grouped_in_sequence_and_use_only_source_text(self):
        records = text_records([
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "attr_key": "main_product", "seq": 2, "value_text": "메모리", "generated_at": None,
             "source_updated_at": None},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "attr_key": "main_product", "seq": 1, "value_text": "스마트폰", "generated_at": None,
             "source_updated_at": None},
        ])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_identity, "company_text:00126380:2025:main_product")
        self.assertEqual(records[0].content, "삼성전자의 2025년 주요 제품은 스마트폰, 메모리입니다.")
        self.assertTrue(records[0].metadata["date_inferred"])

    def test_segment_rows_are_grouped_after_invalid_metrics_are_filtered(self):
        records = segment_records([
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "segment_revenue", "metric_name": "부문 매출",
             "metric_value": Decimal("3"), "unit": "KRW", "verdict": "verified",
             "rcept_no": "20260310002820", "source_updated_at": None},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "segment_employee_count", "metric_name": "부문 직원 수",
             "metric_value": Decimal("5"), "unit": "PERSON", "verdict": "rejected",
             "rcept_no": "20260310002820", "source_updated_at": None},
        ])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].content, "삼성전자의 2025년 DX 부문은 부문 매출 3 KRW입니다.")
        self.assertEqual(records[0].quality, "VERIFIED")

    def test_segment_uses_latest_receipt_date_across_grouped_metrics(self):
        records = segment_records([
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "a_metric", "metric_name": "첫 지표",
             "metric_value": Decimal("1"), "unit": "KRW", "verdict": "verified",
             "rcept_no": "20260310002820", "source_updated_at": None},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "z_metric", "metric_name": "둘째 지표",
             "metric_value": Decimal("2"), "unit": "KRW", "verdict": "verified",
             "rcept_no": "20260410002820", "source_updated_at": None},
        ])

        self.assertEqual(records[0].published_at, datetime(2026, 4, 10, tzinfo=timezone.utc))
        self.assertFalse(records[0].metadata["date_inferred"])
        self.assertEqual(records[0].metadata["rcept_no"], "20260410002820")

    def test_segment_compares_inferred_and_valid_receipt_dates_across_grouped_metrics(self):
        records = segment_records([
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "a_metric", "metric_name": "첫 지표",
             "metric_value": Decimal("1"), "unit": "KRW", "verdict": "verified",
             "rcept_no": "invalid", "source_updated_at": None},
            {"corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
             "segment_name": "DX", "metric_code": "z_metric", "metric_name": "둘째 지표",
             "metric_value": Decimal("2"), "unit": "KRW", "verdict": "verified",
             "rcept_no": "20260410002820", "source_updated_at": None},
        ])

        self.assertEqual(records[0].published_at, datetime(2026, 4, 10, tzinfo=timezone.utc))
        self.assertFalse(records[0].metadata["date_inferred"])
        self.assertEqual(records[0].metadata["rcept_no"], "20260410002820")

    def test_activity_omits_null_values_from_complete_sentence(self):
        record = activity_record({
            "corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
            "activity_type": "facility", "field_name": "반도체", "purpose": None,
            "amount": Decimal("10"), "counterparty": None, "rcept_no": None,
            "source_updated_at": None,
        })

        self.assertEqual(record.content, "삼성전자의 2025년 facility 활동은 반도체, 금액 10입니다.")
        self.assertNotIn("None", record.content)

    def test_activity_identity_uses_meaningful_source_fields_not_database_id(self):
        source = {
            "corp_code": "00126380", "corp_name": "삼성전자", "fiscal_year": 2025,
            "activity_type": "facility", "field_name": "반도체", "purpose": "증설",
            "amount": Decimal("10"), "counterparty": "협력사", "rcept_no": "20260310002820",
            "source_updated_at": "2026-03-10T00:00:00+00:00",
        }
        first = activity_record({**source, "id": 1})
        same_source = activity_record({**source, "id": 999})
        changed_source = activity_record({**source, "id": 1, "purpose": "유지보수"})

        self.assertEqual(first.source_identity, same_source.source_identity)
        self.assertEqual(first.evidence_id, same_source.evidence_id)
        self.assertEqual(first.content_hash, same_source.content_hash)
        self.assertNotEqual(first.source_identity, changed_source.source_identity)
        self.assertNotEqual(first.evidence_id, changed_source.evidence_id)
        self.assertNotEqual(first.content_hash, changed_source.content_hash)

    def test_profile_uses_dart_date_before_updated_at(self):
        record = profile_record({
            "corp_code": "00126380", "corp_name": "삼성전자", "corp_cls": "Y",
            "industry_code": "26", "ceo_nm": "홍길동", "established_date": None,
            "listed_date": None, "dart_modify_date": "20260913",
            "source_updated_at": datetime(2026, 9, 14, tzinfo=timezone.utc),
        })

        self.assertEqual(record.published_at, datetime(2026, 9, 13, tzinfo=timezone.utc))
        self.assertEqual(record.content, "삼성전자는 시장 구분 Y, 산업 코드 26, 대표자 홍길동입니다.")

    def test_content_hash_uses_canonical_payload_order(self):
        first = {
            "title": "매출액", "content": "삼성전자의 2025년 매출액은 1000000 KRW입니다.",
            "metadata": {"metric_code": "revenue", "unit": "KRW"},
        }
        second = {
            "metadata": {"unit": "KRW", "metric_code": "revenue"},
            "content": "삼성전자의 2025년 매출액은 1000000 KRW입니다.", "title": "매출액",
        }

        self.assertEqual(content_hash(first), content_hash(second))
        self.assertRegex(content_hash(first), r"^[0-9a-f]{64}$")

    def test_as_db_row_serializes_metadata_deterministically(self):
        record = EvidenceRecord(
            evidence_id="company-metric-a", corp_code="00126380", source_type="COMPANY_METRIC",
            source_identity="company_metric:00126380:2025:revenue", title="매출액", content="본문",
            reference_period="2025", published_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            source_url=None, quality="VERIFIED", metadata={"b": 2, "a": "가"}, content_hash="0" * 64,
            source_updated_at=None,
        )

        self.assertEqual(record.as_db_row()["metadata"], '{"a":"가","b":2}')


if __name__ == "__main__":
    unittest.main()
