import threading
import time
import unittest

from ai.supervisor.adapters import AgentRegistry
from ai.supervisor.contracts import NoAvailableAgentError, SupervisorPlan
from ai.supervisor.graph import build_supervisor_graph, validate_selected_agents


class FakeModel:
    def __init__(self, plans, aggregate_error=None):
        self.plans = list(plans)
        self.aggregate_error = aggregate_error
        self.plan_errors = []

    def create_plan(self, **kwargs):
        self.plan_errors.append(kwargs["validation_error"])
        return self.plans.pop(0)

    def aggregate(self, **kwargs):
        if self.aggregate_error is not None:
            raise self.aggregate_error
        return "종합 결과"


class RecordingAdapter:
    def __init__(self, name, barrier, fail=False):
        self.name = name
        self.barrier = barrier
        self.fail = fail
        self.threads = []

    def is_available(self, context):
        return context is not None

    def execute(self, instruction, documents, conversation, context):
        self.threads.append(threading.get_ident())
        self.barrier.wait(timeout=1)
        time.sleep(0.01)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        return {"agent": self.name}


def invoke_graph(model, registry, agent_contexts):
    return build_supervisor_graph(model, registry).invoke(
        {
            "instruction": "검토해 줘",
            "documents": [
                {
                    "document_id": "essay",
                    "document_type": "SELF_INTRO",
                    "text": "내용",
                }
            ],
            "conversation": [],
            "agent_contexts": agent_contexts,
            "agent_results": [],
        }
    )


class SupervisorGraphTest(unittest.TestCase):
    def test_rejects_duplicate_unknown_and_unavailable_selections(self):
        with self.assertRaises(ValueError):
            validate_selected_agents(
                SupervisorPlan(selected_agents=["jd", "jd"], reason="중복"),
                ["jd"],
            )
        with self.assertRaises(ValueError):
            validate_selected_agents(
                {"selected_agents": ["unknown"], "reason": "오류"}, ["jd"]
            )
        with self.assertRaises(ValueError):
            validate_selected_agents(
                SupervisorPlan(selected_agents=["position"], reason="불가"),
                ["jd"],
            )

    def test_only_agents_with_context_are_available(self):
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd"], reason="JD 검토")]
        )
        registry = AgentRegistry(
            [
                RecordingAdapter("jd", threading.Barrier(1)),
                RecordingAdapter("position", threading.Barrier(1)),
            ]
        )

        result = invoke_graph(model, registry, {"jd": {"job_context_id": "jctx"}})

        self.assertEqual(result["available_agents"], ["jd"])

    def test_raises_when_no_agent_context_is_available(self):
        registry = AgentRegistry(
            [RecordingAdapter("jd", threading.Barrier(1))]
        )

        with self.assertRaisesRegex(
            NoAvailableAgentError, "no agent context was provided"
        ):
            invoke_graph(FakeModel([]), registry, {})

    def test_valid_plan_calls_model_once(self):
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd"], reason="JD 검토")]
        )
        registry = AgentRegistry(
            [RecordingAdapter("jd", threading.Barrier(1))]
        )

        result = invoke_graph(model, registry, {"jd": {"job_context_id": "jctx"}})

        self.assertEqual(model.plan_errors, [None])
        self.assertEqual(result["final_message"], "종합 결과")

    def test_retries_bad_plan_then_falls_back_to_all_available_agents(self):
        model = FakeModel(
            [
                {"selected_agents": ["unknown"], "reason": "오류"},
                {"selected_agents": ["jd", "jd"], "reason": "중복"},
            ]
        )
        barrier = threading.Barrier(2)
        registry = AgentRegistry(
            [
                RecordingAdapter("jd", barrier),
                RecordingAdapter("position", barrier),
            ]
        )

        result = invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {"position_profile_id": "backend-v1"},
            },
        )

        self.assertEqual(result["plan"].selected_agents, ["jd", "position"])
        self.assertEqual(len(model.plan_errors), 2)
        self.assertIsNone(model.plan_errors[0])
        self.assertIsNotNone(model.plan_errors[1])
        self.assertEqual(
            {item.agent for item in result["agent_results"]}, {"jd", "position"}
        )
        self.assertEqual(len(result["agent_results"]), 2)

    def test_worker_failure_does_not_cancel_other_worker(self):
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd", "position"], reason="둘 다 검토")]
        )
        barrier = threading.Barrier(2)
        registry = AgentRegistry(
            [
                RecordingAdapter("jd", barrier, fail=True),
                RecordingAdapter("position", barrier),
            ]
        )

        result = invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {"position_profile_id": "backend-v1"},
            },
        )

        results = {item.agent: item for item in result["agent_results"]}
        self.assertEqual(results["jd"].status, "FAILED")
        self.assertEqual(results["jd"].error, "RuntimeError: jd failed")
        self.assertEqual(results["position"].status, "SUCCESS")
        self.assertEqual(result["final_message"], "종합 결과")

    def test_selected_agents_execute_in_parallel_threads(self):
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd", "position"], reason="둘 다 검토")]
        )
        barrier = threading.Barrier(2)
        jd = RecordingAdapter("jd", barrier)
        position = RecordingAdapter("position", barrier)
        registry = AgentRegistry([jd, position])

        invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {"position_profile_id": "backend-v1"},
            },
        )

        self.assertEqual(len(jd.threads), 1)
        self.assertEqual(len(position.threads), 1)
        self.assertNotEqual(jd.threads[0], position.threads[0])

    def test_aggregate_failure_uses_deterministic_selected_agent_order(self):
        model = FakeModel(
            [
                SupervisorPlan(
                    selected_agents=["position", "jd"], reason="역순 검토"
                )
            ],
            aggregate_error=RuntimeError("aggregate failed"),
        )
        barrier = threading.Barrier(2)
        registry = AgentRegistry(
            [
                RecordingAdapter("jd", barrier),
                RecordingAdapter("position", barrier),
            ]
        )

        result = invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {"position_profile_id": "backend-v1"},
            },
        )

        self.assertEqual(
            result["final_message"],
            '[position] {"agent": "position"}\n[jd] {"agent": "jd"}',
        )
        self.assertEqual(len(result["agent_results"]), 2)


if __name__ == "__main__":
    unittest.main()
