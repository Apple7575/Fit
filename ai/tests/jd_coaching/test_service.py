import json
import threading
import time
import unittest

from ai.jd_coaching.context_store import InMemoryJobContextStore
from ai.jd_coaching.service import JdAnalysisService


CONFIG = {"base_url": "http://qwen", "model": "qwen", "api_key": "x"}


class FakeQwen:
    def __init__(
        self,
        role_count=2,
        fail_role_id=None,
        fail_once_role_id=None,
        invalid_extraction_once=False,
        delay=0,
    ):
        self.role_count = role_count
        self.fail_role_id = fail_role_id
        self.fail_once_role_id = fail_once_role_id
        self.invalid_extraction_once = invalid_extraction_once
        self.extraction_calls = 0
        self.failed_once = set()
        self.delay = delay
        self.calls = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(self, config, messages, **kwargs):
        schema_name = kwargs["schema_name"]
        self.calls.append(schema_name)
        if schema_name == "jd_requirement_extraction":
            return self._extraction()
        if schema_name == "jd_evidence_decomposition":
            return self._decomposition(messages)
        return self._judgment(messages)

    def _extraction(self):
        self.extraction_calls += 1
        roles = []
        quotes = ["Python API 개발 경험", "서비스 운영 경험"]
        for index in range(self.role_count):
            quote = quotes[index] if index < len(quotes) else f"요구사항 {index + 1}"
            roles.append(
                {
                    "name": quote,
                    "source_quote": quote,
                }
            )
        return {
            "model": "test-qwen",
            "usage": {"total_tokens": 100},
            "output": {"role_elements": roles},
        }

    def _decomposition(self, messages):
        role = json.loads(messages[1]["content"])
        output = {
            "evidence_logic": "ALL",
            "evidence_requirements": [
                {"description": f"{role['name']}의 근거가 명시돼 있다."}
            ],
        }
        if self.invalid_extraction_once and self.extraction_calls == 1:
            self.extraction_calls += 1
            output = {
                "evidence_logic": "ANY",
                "evidence_requirements": [
                    {"description": "대안 1"},
                    {"description": "대안 2"},
                ],
            }
        return {
            "model": "test-qwen",
            "usage": {"total_tokens": 25},
            "output": output,
        }

    def _judgment(self, messages):
        model_input = json.loads(messages[1]["content"])
        role = model_input["role_elements"][0]
        if role["role_element_id"] == self.fail_role_id:
            raise RuntimeError("judge failed")
        if (
            role["role_element_id"] == self.fail_once_role_id
            and role["role_element_id"] not in self.failed_once
        ):
            self.failed_once.add(role["role_element_id"])
            raise ValueError("invalid JSON")
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            judgments = []
            for experience in model_input["experiences"]:
                checks = []
                for requirement in role["evidence_requirements"]:
                    present = (
                        "Python" in experience["text"]
                        and "Java" not in requirement["description"]
                    )
                    checks.append(
                        {
                            "evidence_requirement_id": requirement[
                                "evidence_requirement_id"
                            ],
                            "status": "PRESENT" if present else "ABSENT",
                            "evidence_quote": "Python" if present else "",
                            "reason": "사용자 원문에서 확인했다.",
                        }
                    )
                judgments.append(
                    {
                        "role_element_id": role["role_element_id"],
                        "experience_id": experience["experience_id"],
                        "evidence_checks": checks,
                    }
                )
            return {
                "model": "test-qwen",
                "usage": {"total_tokens": 50},
                "output": {"judgments": judgments},
            }
        finally:
            with self.lock:
                self.active -= 1


class JdAnalysisServiceTest(unittest.TestCase):
    def make_service(self, qwen, max_concurrency=4):
        return JdAnalysisService(
            config=CONFIG,
            policy={},
            qwen_caller=qwen,
            context_store=InMemoryJobContextStore(),
            max_concurrency=max_concurrency,
        )

    def test_reuses_structured_context_for_same_jd(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)

        first = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
        )
        second = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
        )

        self.assertEqual(first["context_id"], second["context_id"])
        self.assertEqual(qwen.calls.count("jd_requirement_extraction"), 1)

    def test_versions_changed_text_for_same_job_posting(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)

        first = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
            job_posting_id="posting-1",
            source_url="https://careers.example.com/jobs/1",
            published_at="2026-09-01",
            valid_until="2026-09-30",
            retrieved_at="2026-09-13",
        )
        second = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험과 서비스 운영 경험",
            job_posting_id="posting-1",
            source_url="https://careers.example.com/jobs/1",
            published_at="2026-09-01",
            valid_until="2026-10-07",
            retrieved_at="2026-09-20",
        )

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual(second["source_url"], "https://careers.example.com/jobs/1")
        self.assertEqual(second["retrieved_at"], "2026-09-20")

    def test_does_not_merge_different_postings_with_same_text(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)

        first = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
            job_posting_id="posting-1",
        )
        second = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
            job_posting_id="posting-2",
        )

        self.assertNotEqual(first["context_id"], second["context_id"])

    def test_retries_invalid_requirement_extraction_once(self):
        qwen = FakeQwen(role_count=1, invalid_extraction_once=True)
        service = self.make_service(qwen)

        context = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
        )

        self.assertEqual(len(context["requirements"]), 1)
        self.assertEqual(qwen.calls.count("jd_requirement_extraction"), 1)
        self.assertEqual(qwen.calls.count("jd_evidence_decomposition"), 2)

    def test_tracks_evidence_to_each_applicant_document(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)
        context = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
        )

        result = service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Java 서버를 개발했습니다.",
                },
                {
                    "document_id": "essay-1",
                    "document_type": "SELF_INTRO",
                    "text": "Python으로 API를 개발했습니다.",
                },
            ],
        )

        evidence = result["requirements"][0]["present_evidence"]
        self.assertEqual(result["requirements"][0]["label"], "SUPPORTED")
        self.assertEqual(evidence[0]["document_id"], "essay-1")
        self.assertEqual(evidence[0]["document_type"], "SELF_INTRO")
        self.assertEqual(evidence[0]["start_offset"], 0)
        self.assertEqual(evidence[0]["end_offset"], len("Python"))

    def test_returns_actionable_feedback_for_missing_evidence(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)
        context = service.create_context(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
        )

        result = service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Java 서버를 개발했습니다.",
                }
            ],
        )

        requirement = result["requirements"][0]
        self.assertEqual(requirement["label"], "NOT_SUPPORTED")
        self.assertTrue(requirement["suggested_actions"])
        self.assertTrue(requirement["follow_up_questions"])
        self.assertIn(
            requirement["missing_evidence"][0]["description"],
            requirement["suggested_actions"][0],
        )

    def test_limits_parallel_judgments(self):
        qwen = FakeQwen(role_count=4, delay=0.03)
        service = self.make_service(qwen, max_concurrency=2)
        context = service.create_context(
            company_name="다른기업",
            position_name="개발자",
            jd_text="Python API 개발 경험 서비스 운영 경험 요구사항 3 요구사항 4",
        )

        service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Python으로 개발했습니다.",
                }
            ],
        )

        self.assertEqual(qwen.max_active, 2)

    def test_returns_successes_when_one_requirement_fails(self):
        qwen = FakeQwen(role_count=2, fail_role_id="role-002")
        service = self.make_service(qwen)
        context = service.create_context(
            company_name="다른기업",
            position_name="개발자",
            jd_text="Python API 개발 경험 서비스 운영 경험",
        )

        result = service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Python으로 개발했습니다.",
                }
            ],
        )

        self.assertEqual(len(result["requirements"]), 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(
            result["failed_requirements"][0]["requirement_id"], "role-002"
        )

    def test_retries_one_transient_judge_failure(self):
        qwen = FakeQwen(role_count=1, fail_once_role_id="role-001")
        service = self.make_service(qwen)
        context = service.create_context(
            company_name="다른기업",
            position_name="개발자",
            jd_text="Python API 개발 경험",
        )

        result = service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Python으로 개발했습니다.",
                }
            ],
        )

        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(qwen.calls.count("jd_pairwise_evidence_judge"), 2)

    def test_analyze_keeps_single_text_compatibility(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)

        result = service.analyze(
            company_name="다른기업",
            position_name="백엔드 개발자",
            jd_text="Python API 개발 경험",
            applicant_text="Python으로 데이터 처리 도구를 만들었습니다.",
        )

        self.assertEqual(result["requirements"][0]["label"], "SUPPORTED")
        self.assertEqual(result["usage"]["total_tokens"], 175)

    def test_any_logic_is_supported_when_one_alternative_is_present(self):
        qwen = FakeQwen(role_count=1)
        service = self.make_service(qwen)
        context = service.create_context(
            company_name="다른기업",
            position_name="개발자",
            jd_text="Python API 개발 경험",
        )
        stored = service._context_store.get(context["context_id"])
        stored.role_elements[0]["evidence_logic"] = "ANY"
        stored.role_elements[0]["evidence_requirements"].append(
            {
                "evidence_requirement_id": "role-001-evidence-002",
                "description": "Java 경험",
            }
        )

        result = service.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "resume-1",
                    "document_type": "RESUME",
                    "text": "Python으로 개발했습니다.",
                }
            ],
        )

        self.assertEqual(result["requirements"][0]["label"], "SUPPORTED")


if __name__ == "__main__":
    unittest.main()
