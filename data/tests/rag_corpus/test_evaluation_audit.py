import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.rag_corpus.evaluation_audit import audit_case
from scripts.audit_company_retrieval_eval import main


class EvaluationAuditTest(unittest.TestCase):
    def case(self, **changes):
        value = {
            "case_id": "case-1", "validation_status": "AUTO_VALIDATED",
            "published_at": "2026-03-10", "question": "주요 사업은 무엇인가?",
            "answer": "광고 사업", "gold_evidence": {
                "kind": "paragraph", "source_quote": "회사는 광고 사업을 운영합니다.",
            },
        }
        value.update(changes)
        return value

    def test_numeric_table_row_without_complete_context_is_not_reviewable(self):
        case = self.case(
            question="현대아산 최초취득금액은 몇 원인가?", answer="22,500원",
            gold_evidence={"kind": "table_row", "source_quote": "현대아산 | 단순투자 | 22,500 | 149,999"},
        )
        result = audit_case(case)
        self.assertEqual(result["audit_status"], "NEEDS_CONTEXT")
        self.assertIn("table_numeric_context_unverified", result["reasons"])

    def test_textual_table_row_is_also_held_without_column_context(self):
        case = self.case(
            question="현대아산 투자 목적은?", answer="단순투자",
            gold_evidence={"kind": "table_row", "source_quote": "현대아산 | 단순투자"},
        )
        result = audit_case(case)
        self.assertEqual(result["audit_status"], "NEEDS_CONTEXT")
        self.assertIn("table_column_context_unverified", result["reasons"])

    def test_percentage_denominator_claim_requires_explicit_quote(self):
        case = self.case(
            question="DX 매출은 전체 매출 중 몇 퍼센트인가?", answer="56.3%",
            gold_evidence={"kind": "paragraph", "source_quote": "DX 매출은 187조원(56.3%)입니다."},
        )
        result = audit_case(case)
        self.assertIn("denominator_not_explicit", result["reasons"])

    def test_future_fiscal_year_is_held_for_review(self):
        case = self.case(
            question="2027년 사업연도 투자금액은?", answer="10억 원",
            gold_evidence={"kind": "paragraph", "source_quote": "2027년 사업연도 투자금액은 10억 원입니다."},
        )
        result = audit_case(case)
        self.assertIn("year_after_publication", result["reasons"])

    def test_direct_paragraph_answer_remains_reviewable_not_gold(self):
        result = audit_case(self.case())
        self.assertEqual(result["audit_status"], "REVIEWABLE")
        self.assertEqual(result["reasons"], [])

    def test_existing_rejection_stays_rejected(self):
        result = audit_case(self.case(validation_status="REJECTED"))
        self.assertEqual(result["audit_status"], "REJECTED_ORIGINAL")

    def test_cli_writes_separate_audit_without_changing_source(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "silver.jsonl"
            target = Path(directory) / "audit.jsonl"
            original = json.dumps(self.case(), ensure_ascii=False) + "\n"
            source.write_text(original, encoding="utf-8")
            self.assertEqual(main(["--input", str(source), "--output", str(target)]), 0)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            audited = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(audited["case_id"], "case-1")
            self.assertEqual(audited["audit_status"], "REVIEWABLE")


if __name__ == "__main__":
    unittest.main()
