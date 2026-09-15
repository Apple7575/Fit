import unittest

from ai.supervisor.adapters import AgentRegistry, JdAgentAdapter, PositionAgentAdapter


class FakeJdService:
    def __init__(self):
        self.calls = []

    def analyze_documents(self, context_id, documents):
        self.calls.append((context_id, documents))
        return {"context_id": context_id}


class FakePositionService:
    def __init__(self):
        self.calls = []

    def analyze(self, rubric_id, position_context, documents, conversation):
        self.calls.append((rubric_id, position_context, documents, conversation))
        return {"rubric": {"id": rubric_id}, "position_context": position_context}


class AgentRegistryTest(unittest.TestCase):
    def test_resolves_context_backed_agents_and_calls_services_directly(self):
        jd = FakeJdService()
        position = FakePositionService()
        registry = AgentRegistry([JdAgentAdapter(jd), PositionAgentAdapter(position)])
        contexts = {
            "jd": {"job_context_id": "jctx_1"},
            "position": {
                "rubric_id": "experience-depth-v1",
                "position_context": {
                    "position_name": "백엔드 개발자",
                    "priority_requirements": ["Spring 기반 API 개발"],
                },
            },
        }
        documents = [
            {"document_id": "resume-1", "document_type": "RESUME", "text": "이력"},
            {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "자소서"},
            {"document_id": "experience-1", "document_type": "EXPERIENCE", "text": "경험"},
            {"document_id": "portfolio-1", "document_type": "PORTFOLIO", "text": "포트폴리오"},
        ]
        position_documents = [documents[1], documents[2]]

        self.assertEqual(registry.available_names(contexts), ["jd", "position"])
        registry.execute("jd", "검토", documents, [], contexts["jd"])
        registry.execute("position", "검토", documents, [], contexts["position"])

        self.assertEqual(jd.calls[0][0], "jctx_1")
        self.assertEqual(position.calls, [(
            "experience-depth-v1",
            {
                "position_name": "백엔드 개발자",
                "priority_requirements": ["Spring 기반 API 개발"],
            },
            position_documents,
            [],
        )])

    def test_position_rejects_request_without_supported_documents(self):
        position = FakePositionService()
        adapter = PositionAgentAdapter(position)
        context = {
            "rubric_id": "experience-depth-v1",
            "position_context": {
                "position_name": "백엔드 개발자",
                "priority_requirements": [],
            },
        }

        with self.assertRaisesRegex(
            ValueError, "position agent requires SELF_INTRO or EXPERIENCE document"
        ):
            adapter.execute(
                "검토",
                [{"document_id": "resume-1", "document_type": "RESUME", "text": "이력"}],
                [],
                context,
            )

        self.assertEqual(position.calls, [])


if __name__ == "__main__":
    unittest.main()
