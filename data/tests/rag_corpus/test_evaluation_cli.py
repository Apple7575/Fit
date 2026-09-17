import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_company_retrieval_eval import main


class EvaluationCliTest(unittest.TestCase):
    def test_marks_fallback_report_and_keeps_actual_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            (archive / "manifest.csv").write_text(
                "corp_name,corp_code,year,rcept_no,rcept_dt,file,report_nm\n"
                "회사,00126380,2024,20250318000001,20250318,older.xml,사업보고서\n"
                "회사,00126380,2025,20260318000001,20260318,latest.xml,사업보고서\n",
                encoding="utf-8",
            )
            (archive / "older.xml").write_text(
                "<DOCUMENT><TITLE>사업 현황</TITLE><P>반도체 사업을 운영합니다.</P></DOCUMENT>",
                encoding="utf-8",
            )
            (archive / "latest.xml").write_text("<DOCUMENT><TITLE>파손</TITLE>", encoding="utf-8")
            selection = root / "selection.json"
            selection.write_text(json.dumps({
                "selection_version": "test-v1",
                "companies": [{"corp_code": "00126380", "group": "tuning"}],
            }), encoding="utf-8")
            env_file = root / ".env"
            env_file.write_text("QWEN_BASE_URL=https://example.test/v1\nQWEN_MODEL=test\nQWEN_API_KEY=secret\n")
            output = root / "cases.jsonl"

            class Client:
                def __init__(self, base_url, model, api_key):
                    if (base_url, model, api_key) != ("https://example.test/v1", "test", "secret"):
                        raise AssertionError("explicit env file was ignored")

                def generate(self, _category, units):
                    unit = units[0]
                    return {"question": "주요 사업은?", "answer": "반도체 사업",
                            "section_index": unit["section_index"], "kind": unit["kind"],
                            "source_index": unit["source_index"],
                            "source_quote": "반도체 사업을 운영합니다"}

                def judge(self, _candidate, _source):
                    return {"supported": True, "reason": "source confirms"}

            with patch.dict(os.environ, {"QWEN_BASE_URL": "stale", "QWEN_MODEL": "stale", "QWEN_API_KEY": "stale"}), patch(
                "scripts.build_company_retrieval_eval.QwenEvaluationClient", Client,
            ):
                result = main([
                    "--selection", str(selection), "--dart-archive", str(archive),
                    "--output", str(output), "--as-of", "2026-09-16", "--limit", "1",
                    "--env-file", str(env_file),
                ])
            self.assertEqual(result, 0)
            case = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(case["rcept_no"], "20250318000001")
            self.assertEqual(case["source_report_year"], 2024)
            self.assertEqual(case["source_status"], "FALLBACK_PRIOR_REPORT")
            self.assertEqual(case["skipped_reports"][0]["rcept_no"], "20260318000001")
            coverage = json.loads(output.with_suffix(".jsonl.coverage.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(coverage["missing_categories"]["PERFORMANCE"], "NO_GROUNDED_CANDIDATE")

    def test_company_without_grounded_source_is_recorded_and_not_regenerated_on_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "archive"
            archive.mkdir()
            (archive / "manifest.csv").write_text(
                "corp_name,corp_code,year,rcept_no,rcept_dt,file,report_nm\n"
                "회사,00126380,2025,20260318000001,20260318,report.xml,사업보고서\n",
                encoding="utf-8",
            )
            (archive / "report.xml").write_text(
                "<DOCUMENT><TITLE>기타 사항</TITLE><P>내용이 없습니다.</P></DOCUMENT>", encoding="utf-8",
            )
            selection = root / "selection.json"
            selection.write_text(json.dumps({"selection_version": "test-v1", "companies": [
                {"corp_code": "00126380", "group": "tuning"},
            ]}), encoding="utf-8")
            env_file = root / ".env"
            env_file.write_text("QWEN_BASE_URL=https://example.test/v1\nQWEN_MODEL=test\nQWEN_API_KEY=secret\n")
            output = root / "cases.jsonl"

            class Client:
                def __init__(self, *_args):
                    pass

                def generate(self, *_args):
                    raise AssertionError("후보가 없으면 생성 호출도 없어야 합니다")

                def judge(self, *_args):
                    raise AssertionError("후보가 없으면 검증 호출도 없어야 합니다")

            args = ["--selection", str(selection), "--dart-archive", str(archive),
                    "--output", str(output), "--as-of", "2026-09-16", "--limit", "1",
                    "--env-file", str(env_file)]
            with patch("scripts.build_company_retrieval_eval.QwenEvaluationClient", Client):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args), 0)
            coverage_path = output.with_suffix(".jsonl.coverage.jsonl")
            self.assertEqual(len(coverage_path.read_text(encoding="utf-8").splitlines()), 1)
            summary = json.loads(output.with_suffix(".jsonl.summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["completed_companies"], 1)
            self.assertEqual(summary["missing_categories"]["PERFORMANCE"], 1)


if __name__ == "__main__":
    unittest.main()
