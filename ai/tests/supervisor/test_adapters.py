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

    def analyze(self, profile_id, documents, conversation):
        self.calls.append((profile_id, documents, conversation))
        return {"position_profile": {"id": profile_id}}


class AgentRegistryTest(unittest.TestCase):
    def test_resolves_context_backed_agents_and_calls_services_directly(self):
        jd = FakeJdService()
        position = FakePositionService()
        registry = AgentRegistry([JdAgentAdapter(jd), PositionAgentAdapter(position)])
        contexts = {
            "jd": {"job_context_id": "jctx_1"},
            "position": {"position_profile_id": "backend-v1"},
        }
        documents = [{"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "내용"}]

        self.assertEqual(registry.available_names(contexts), ["jd", "position"])
        registry.execute("jd", "검토", documents, [], contexts["jd"])
        registry.execute("position", "검토", documents, [], contexts["position"])

        self.assertEqual(jd.calls[0][0], "jctx_1")
        self.assertEqual(position.calls[0][0], "backend-v1")


if __name__ == "__main__":
    unittest.main()
