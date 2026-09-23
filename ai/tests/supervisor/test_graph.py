import json
import threading
import time
import unittest
from unittest.mock import patch

from ai.supervisor.adapters import AgentRegistry, NewsAgentAdapter
from ai.llm.contracts import LlmRateLimitedError
from ai.tests.news_intelligence.test_service import build_service, REQUEST
from ai.supervisor.contracts import NoAvailableAgentError, SupervisorPlan
from ai.supervisor.graph import build_supervisor_graph, validate_selected_agents
from ai.supervisor.model import QwenSupervisorModel


class FakeModel:
    def __init__(self, plans, aggregate_error=None):
        self.plans = list(plans)
        self.aggregate_error = aggregate_error
        self.plan_errors = []
        self.aggregate_calls = []

    def create_plan(self, **kwargs):
        self.plan_errors.append(kwargs["validation_error"])
        return self.plans.pop(0)

    def aggregate(self, **kwargs):
        self.aggregate_calls.append(kwargs)
        if self.aggregate_error is not None:
            raise self.aggregate_error
        return "종합 결과"


class RecordingAdapter:
    def __init__(
        self,
        name,
        barrier=None,
        fail=False,
        error=None,
        result=None,
        execution_log=None,
        lifecycle_log=None,
    ):
        self.name = name
        self.barrier = barrier
        self.fail = fail
        self.error = error
        self.result = result
        self.execution_log = execution_log
        self.lifecycle_log = lifecycle_log
        self.threads = []
        self.passed_barrier = False
        self.prior_agents = []
        self.passed_barrier = False

    def is_available(self, context):
        return context is not None

    def execute(self, instruction, documents, conversation, context, prior_results=()):
        self.threads.append(threading.get_ident())
        self.prior_agents = [item.agent for item in prior_results]
        if self.lifecycle_log is not None:
            self.lifecycle_log.append(f"{self.name}:started")
        if self.execution_log is not None:
            self.execution_log.append(self.name)
        if self.barrier is not None:
            self.barrier.wait(timeout=2)
            self.passed_barrier = True
        time.sleep(0.01)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        if self.error is not None:
            raise self.error
        if self.lifecycle_log is not None:
            self.lifecycle_log.append(f"{self.name}:finished")
        return self.result or {"agent": self.name}


class FakeQwenCaller:
    def __init__(self, plan_outputs):
        self.plan_outputs = list(plan_outputs)
        self.plan_calls = []

    def __call__(self, config, messages, **kwargs):
        if kwargs["schema_name"] == "supervisor_aggregate_v2":
            # 성공한 담당이 하나뿐인 경우에 통과하는 최소 출력
            return {"output": {
                "answer": "종합 결과",
                "judgments": [{"claim": "담당 결과를 바탕으로 보완이 필요하다.", "agents": ["news"], "evidence_ids": []}],
                "conflicts": [],
                "next_action": "문항을 보완한다.",
            }}
        self.plan_calls.append(messages)
        output = self.plan_outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return {"output": output}


def invoke_graph(model, registry, agent_contexts, agent_selection="auto"):
    return build_supervisor_graph(model, registry).invoke(
        {
            "agent_selection": agent_selection,
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


def all_contexts():
    return {
        "jd": {"job_context_id": "jctx"},
        "position": {
            "rubric_id": "experience-depth-v1",
            "position_context": {
                "position_name": "백엔드 개발자",
                "priority_requirements": [],
            },
        },
        "writing": {"question": "협업 경험", "char_limit": 700},
    }


class SupervisorGraphTest(unittest.TestCase):
    def test_aggregate_fallback_never_exposes_worker_json(self):
        result = invoke_graph(
            FakeModel(
                [SupervisorPlan(selected_agents=["jd"], reason="JD 검토")],
                aggregate_error=RuntimeError("aggregate unavailable"),
            ),
            AgentRegistry([
                RecordingAdapter("jd", result={"message": "요구 역량을 보강하세요.", "score": 72})
            ]),
            {"jd": {"job_context_id": "jctx"}},
        )

        self.assertEqual(result["final_message"], "### JD 검토\n요구 역량을 보강하세요.")
        self.assertNotIn('"score"', result["final_message"])

    def test_marks_gms_rate_limit_with_stable_worker_error_code(self):
        result = invoke_graph(
            FakeModel([SupervisorPlan(selected_agents=["jd"], reason="JD 검토")]),
            AgentRegistry([
                RecordingAdapter("jd", error=LlmRateLimitedError("GMS", 10))
            ]),
            {"jd": {"job_context_id": "jctx"}},
        )

        self.assertEqual(result["agent_results"][0].status, "FAILED")
        self.assertEqual(result["agent_results"][0].error, "GMS_RATE_LIMITED")

    def test_real_news_response_survives_qwen_and_fallback_aggregation(self):
        service, _, _, _ = build_service()
        for fallback in (False, True):
            with self.subTest(fallback=fallback):
                caller = FakeQwenCaller([{"selected_agents": ["news"], "reason": "news"}])
                model = QwenSupervisorModel({}, qwen_caller=caller)
                if fallback:
                    model = FakeModel(
                        [SupervisorPlan(selected_agents=["news"], reason="news")],
                        aggregate_error=RuntimeError("offline"),
                    )
                output = invoke_graph(model, AgentRegistry([NewsAgentAdapter(service)]), {
                    "news": {"job_context_id": REQUEST.job_context_id, "corp_code": REQUEST.corp_code},
                })
                result = output["agent_results"][0]
                self.assertEqual(result.status, "SUCCESS")
                payload = json.loads(json.dumps(result.result))
                self.assertEqual(payload["analysis"]["window"]["to"], "2026-09-16")
                source = payload["analysis"]["signals"][0]["sources"][0]
                self.assertEqual(source["published_at"], "2026-09-15T12:00:00Z")
                self.assertEqual(source["url"], "https://example.test/stored/1")
                if fallback:
                    self.assertTrue(output["final_message"].startswith("### 뉴스 분석\n"))
                    self.assertNotIn('"analysis"', output["final_message"])
                else:
                    self.assertTrue(output["final_message"].startswith("종합 결과"))

    def test_dispatches_three_selected_workers_in_parallel(self):
        barrier = threading.Barrier(3, timeout=2)
        adapters = [
            RecordingAdapter(name, barrier) for name in ("jd", "position", "news")
        ]
        graph = build_supervisor_graph(
            FakeModel([
                SupervisorPlan(
                    selected_agents=["jd", "position", "news"], reason="모두 필요"
                )
            ]),
            AgentRegistry(adapters),
        )

        output = graph.invoke({
            "instruction": "함께 검토해줘",
            "documents": [{
                "document_id": "essay",
                "document_type": "SELF_INTRO",
                "text": "내용",
            }],
            "conversation": [],
            "agent_contexts": {
                "jd": {"job_context_id": "jctx"},
                "position": {"rubric_id": "experience-depth-v1", "position_context": {}},
                "news": {"job_context_id": "jctx", "corp_code": "00126380"},
            },
            "agent_results": [],
        })

        self.assertEqual(
            {item.agent for item in output["agent_results"]},
            {"jd", "position", "news"},
        )
        self.assertTrue(
            all(item.status == "SUCCESS" for item in output["agent_results"])
        )
        self.assertTrue(all(adapter.passed_barrier for adapter in adapters))

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
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": [],
                    },
                },
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

    def test_real_model_retries_validation_error_then_uses_valid_plan(self):
        caller = FakeQwenCaller(
            [
                {"selected_agents": ["unknown"], "reason": "오류"},
                {"selected_agents": ["jd"], "reason": "재계획"},
            ]
        )
        model = QwenSupervisorModel({}, qwen_caller=caller)
        registry = AgentRegistry(
            [RecordingAdapter("jd", threading.Barrier(1))]
        )

        result = invoke_graph(model, registry, {"jd": {"job_context_id": "jctx"}})

        self.assertEqual(result["plan"].selected_agents, ["jd"])
        self.assertEqual(len(caller.plan_calls), 2)
        retry_payload = json.loads(caller.plan_calls[1][1]["content"])
        self.assertIn("previous_validation_error", retry_payload)

    def test_real_model_falls_back_after_two_validation_errors(self):
        caller = FakeQwenCaller(
            [
                {"selected_agents": ["unknown"], "reason": "첫 오류"},
                {"selected_agents": ["other"], "reason": "둘째 오류"},
            ]
        )
        model = QwenSupervisorModel({}, qwen_caller=caller)
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
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": [],
                    },
                },
            },
        )

        self.assertEqual(result["plan"].selected_agents, ["jd", "position"])
        self.assertEqual(len(caller.plan_calls), 2)

    def test_real_model_operational_error_is_not_converted_to_fallback(self):
        caller = FakeQwenCaller([RuntimeError("Qwen unavailable")])
        model = QwenSupervisorModel({}, qwen_caller=caller)
        registry = AgentRegistry(
            [RecordingAdapter("jd", threading.Barrier(1))]
        )

        with self.assertRaisesRegex(RuntimeError, "Qwen unavailable"):
            invoke_graph(model, registry, {"jd": {"job_context_id": "jctx"}})

        self.assertEqual(len(caller.plan_calls), 1)

    def test_invalid_qwen_url_propagates_without_worker_calls(self):
        model = QwenSupervisorModel(
            {"base_url": "invalid-url", "model": "qwen", "api_key": "test"}
        )
        worker = RecordingAdapter("jd", threading.Barrier(1))

        with self.assertRaisesRegex(ValueError, "unknown url type"):
            invoke_graph(
                model, AgentRegistry([worker]), {"jd": {"job_context_id": "jctx"}}
            )

        self.assertEqual(worker.threads, [])

    def test_operational_value_type_and_key_errors_propagate_without_workers(self):
        for error in (
            ValueError("bad config"), TypeError("bad request"), KeyError("model")
        ):
            with self.subTest(error=type(error).__name__):
                caller = FakeQwenCaller([error, error])
                worker = RecordingAdapter("jd", threading.Barrier(1))
                with self.assertRaises(type(error)) as caught:
                    invoke_graph(
                        QwenSupervisorModel({}, qwen_caller=caller),
                        AgentRegistry([worker]),
                        {"jd": {"job_context_id": "jctx"}},
                    )
                self.assertIs(caught.exception, error)
                self.assertEqual(worker.threads, [])
                self.assertEqual(len(caller.plan_calls), 1)

    def test_real_caller_invalid_json_retries_then_falls_back(self):
        model = QwenSupervisorModel(
            {"base_url": "http://qwen.test", "model": "qwen", "api_key": "test"}
        )
        worker = RecordingAdapter("jd", threading.Barrier(1))
        with patch("ai.llm.vllm.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = (
                b'{"choices": [{"message": {"content": "not JSON"}}]}'
            )
            result = invoke_graph(
                model, AgentRegistry([worker]), {"jd": {"job_context_id": "jctx"}}
            )

        self.assertIn("fallback", result["plan"].reason)
        self.assertEqual(len(worker.threads), 1)
        # Two plan attempts plus one aggregation attempt after the worker succeeds.
        self.assertEqual(urlopen.call_count, 3)

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
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": [],
                    },
                },
            },
        )

        results = {item.agent: item for item in result["agent_results"]}
        self.assertEqual(results["jd"].status, "FAILED")
        self.assertEqual(results["jd"].error, "RuntimeError: jd failed")
        self.assertEqual(results["position"].status, "SUCCESS")
        self.assertEqual(result["final_message"], "종합 결과")

    def test_writing_only_skips_analysis_stage(self):
        execution_log = []
        jd = RecordingAdapter("jd", execution_log=execution_log)
        position = RecordingAdapter("position", execution_log=execution_log)
        writing = RecordingAdapter(
            "writing",
            result={
                "status": "REVISED",
                "message": "첨삭 결과",
                "revision": "수정된 자기소개서",
            },
            execution_log=execution_log,
        )
        registry = AgentRegistry([jd, position, writing])
        model = FakeModel(
            [SupervisorPlan(selected_agents=["writing"], reason="첨삭")]
        )

        result = invoke_graph(
            model,
            registry,
            all_contexts(),
        )

        self.assertEqual(execution_log, ["writing"])
        self.assertEqual(result["final_message"], "첨삭 결과")
        self.assertEqual(model.aggregate_calls, [])
        self.assertEqual(
            {item.agent: item.status for item in result["agent_results"]},
            {"writing": "SUCCESS"},
        )

    def test_analysis_finishes_before_writing_and_passes_successes(self):
        analysis_barrier = threading.Barrier(2)
        lifecycle_log = []
        jd = RecordingAdapter("jd", analysis_barrier, lifecycle_log=lifecycle_log)
        position = RecordingAdapter(
            "position", analysis_barrier, lifecycle_log=lifecycle_log
        )
        writing = RecordingAdapter("writing", lifecycle_log=lifecycle_log)
        registry = AgentRegistry([jd, position, writing])

        invoke_graph(
            FakeModel(
                [
                    SupervisorPlan(
                        selected_agents=["jd", "position", "writing"],
                        reason="분석 후 첨삭",
                    )
                ]
            ),
            registry,
            all_contexts(),
        )

        self.assertLess(
            lifecycle_log.index("jd:finished"),
            lifecycle_log.index("writing:started"),
        )
        self.assertLess(
            lifecycle_log.index("position:finished"),
            lifecycle_log.index("writing:started"),
        )
        self.assertEqual(writing.prior_agents, ["jd", "position"])

    def test_writing_receives_only_successful_analysis_results(self):
        analysis_barrier = threading.Barrier(2)
        jd = RecordingAdapter("jd", analysis_barrier, fail=True)
        position = RecordingAdapter("position", analysis_barrier)
        writing = RecordingAdapter("writing")
        registry = AgentRegistry([jd, position, writing])

        result = invoke_graph(
            FakeModel(
                [
                    SupervisorPlan(
                        selected_agents=["jd", "position", "writing"],
                        reason="분석 후 첨삭",
                    )
                ]
            ),
            registry,
            all_contexts(),
        )

        results = {item.agent: item for item in result["agent_results"]}
        self.assertEqual(results["jd"].status, "FAILED")
        self.assertEqual(results["position"].status, "SUCCESS")
        self.assertEqual(results["writing"].status, "SUCCESS")
        self.assertEqual(writing.prior_agents, ["position"])

    def test_writing_runs_without_prior_results_when_all_analyses_fail(self):
        analysis_barrier = threading.Barrier(2)
        jd = RecordingAdapter("jd", analysis_barrier, fail=True)
        position = RecordingAdapter("position", analysis_barrier, fail=True)
        writing = RecordingAdapter("writing")
        registry = AgentRegistry([jd, position, writing])

        result = invoke_graph(
            FakeModel(
                [
                    SupervisorPlan(
                        selected_agents=["jd", "position", "writing"],
                        reason="분석 후 첨삭",
                    )
                ]
            ),
            registry,
            all_contexts(),
        )

        results = {item.agent: item for item in result["agent_results"]}
        self.assertEqual(results["jd"].status, "FAILED")
        self.assertEqual(results["position"].status, "FAILED")
        self.assertEqual(results["writing"].status, "SUCCESS")
        self.assertEqual(writing.prior_agents, [])

    def test_writing_failure_keeps_successful_analysis_results(self):
        analysis_barrier = threading.Barrier(2)
        jd = RecordingAdapter("jd", analysis_barrier)
        position = RecordingAdapter("position", analysis_barrier)
        writing = RecordingAdapter("writing", fail=True)
        registry = AgentRegistry([jd, position, writing])

        result = invoke_graph(
            FakeModel(
                [
                    SupervisorPlan(
                        selected_agents=["jd", "position", "writing"],
                        reason="분석 후 첨삭",
                    )
                ]
            ),
            registry,
            all_contexts(),
        )

        self.assertEqual(
            {item.agent: item.status for item in result["agent_results"]},
            {"jd": "SUCCESS", "position": "SUCCESS", "writing": "FAILED"},
        )
        self.assertEqual(result["final_message"], "종합 결과")

    def test_clarification_result_is_forwarded_without_aggregation(self):
        clarification = "본인이 수행한 행동을 알려주세요."
        model = FakeModel(
            [SupervisorPlan(selected_agents=["writing"], reason="추가 정보 필요")]
        )
        writing = RecordingAdapter(
            "writing",
            result={
                "status": "CLARIFICATION_REQUIRED",
                "message": clarification,
                "revision": None,
            },
        )

        result = invoke_graph(
            model,
            AgentRegistry([writing]),
            {"writing": {"question": "협업 경험", "char_limit": 700}},
        )

        self.assertEqual(result["final_message"], clarification)
        self.assertEqual(model.aggregate_calls, [])

    def test_clarification_is_appended_when_other_agents_answered(self):
        """되물음만 내보내면 다른 담당이 낸 답이 묻힌다. 종합을 먼저 내고 끝에 붙인다."""
        clarification = "본인이 수행한 행동을 알려주세요."
        model = FakeModel(
            [SupervisorPlan(selected_agents=["company", "writing"], reason="둘 다 본다")]
        )
        company = RecordingAdapter("company", result={"message": "매출 186.3조원"})
        writing = RecordingAdapter(
            "writing",
            result={
                "status": "CLARIFICATION_REQUIRED",
                "message": clarification,
                "revision": None,
            },
        )

        result = invoke_graph(
            model,
            AgentRegistry([company, writing]),
            {
                "company": {"corp_code": "00164742"},
                "writing": {"question": "협업 경험", "char_limit": 700},
            },
        )

        self.assertIn("종합 결과", result["final_message"])
        self.assertTrue(result["final_message"].endswith(clarification))
        self.assertEqual(len(model.aggregate_calls), 1)

    def test_agent_selection_all_runs_every_available_agent_without_planning(self):
        """첫 자동 검토는 고를 질문이 없다. 계획 모델을 부르면 대부분이 '필요 없다' 로 남는다."""
        model = FakeModel([])  # 계획을 부르면 pop 에서 터진다
        jd = RecordingAdapter("jd")
        position = RecordingAdapter("position")

        result = invoke_graph(
            model,
            AgentRegistry([jd, position]),
            {
                "jd": {"job_context_id": "jctx"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {"position_name": "백엔드", "priority_requirements": []},
                },
            },
            agent_selection="all",
        )

        self.assertEqual(
            sorted(item.agent for item in result["agent_results"]), ["jd", "position"]
        )
        self.assertEqual(model.plan_errors, [])  # 계획 모델을 부르지 않았다

    def test_selected_agents_execute_in_parallel_threads(self):
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd", "position"], reason="둘 다 검토")]
        )
        barrier = threading.Barrier(2)
        jd = RecordingAdapter("jd", barrier)
        position = RecordingAdapter("position", barrier)
        registry = AgentRegistry([jd, position])

        result = invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": [],
                    },
                },
            },
        )

        self.assertEqual(len(jd.threads), 1)
        self.assertEqual(len(position.threads), 1)
        self.assertNotEqual(jd.threads[0], position.threads[0])
        self.assertEqual(
            {item.agent: item.status for item in result["agent_results"]},
            {"jd": "SUCCESS", "position": "SUCCESS"},
        )

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
        # 종합이 실패하면 담당들이 낸 문장을 대신 이어 붙인다. 예전에는 결과 dict 를 통째로
        # json.dumps 해서 내부 구조가 화면에 드러났다. 여기서 보려는 것은 그 문장이 계획한
        # 순서(position → jd)대로 붙는가이므로, 담당마다 읽을 수 있는 문장을 갖게 둔다.
        registry = AgentRegistry(
            [
                RecordingAdapter("jd", barrier, result={"message": "jd 의견"}),
                RecordingAdapter("position", barrier, result={"message": "position 의견"}),
            ]
        )

        result = invoke_graph(
            model,
            registry,
            {
                "jd": {"job_context_id": "jctx"},
                "position": {
                    "rubric_id": "experience-depth-v1",
                    "position_context": {
                        "position_name": "백엔드 개발자",
                        "priority_requirements": [],
                    },
                },
            },
        )

        self.assertEqual(
            result["final_message"],
            "### 경험 분석\nposition 의견\n\n### JD 검토\njd 의견",
        )
        self.assertEqual(len(result["agent_results"]), 2)

    def test_aggregate_failure_without_readable_text_does_not_leak_internals(self):
        """읽을 문장이 없으면 결과 dict 를 화면에 쏟지 않는다.

        예전에는 여기서 담당 결과를 통째로 json.dumps 해서 말풍선에 넣었다. 사용자에게
        아무 뜻도 없는 데다, 내부 구조가 새어 나온 것처럼 보인다.
        """
        model = FakeModel(
            [SupervisorPlan(selected_agents=["jd"], reason="검토")],
            aggregate_error=RuntimeError("aggregate failed"),
        )
        registry = AgentRegistry([RecordingAdapter("jd", result={"internal_id": "x-1"})])

        result = invoke_graph(model, registry, {"jd": {"job_context_id": "jctx"}})

        self.assertNotIn("internal_id", result["final_message"])
        self.assertIn("다시 시도", result["final_message"])


if __name__ == "__main__":
    unittest.main()
