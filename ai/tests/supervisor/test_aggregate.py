import unittest

from ai.supervisor.aggregate import (
    AggregateOutputError,
    available_evidence_ids,
    render_aggregate,
    validate_aggregate,
)
from ai.supervisor.contracts import AgentResult, Evidence


def evidence(evidence_id, agent):
    return Evidence(evidence_id=evidence_id, source_type="JOB_POSTING", source_id="s", agent=agent)


JD = AgentResult(
    agent="jd", status="SUCCESS",
    result={"message": "Spring 기반 API 개발 요구사항에 대한 근거가 자소서에 없습니다."},
    evidence=[evidence("jd:ctx1", "jd")],
)
NEWS = AgentResult(
    agent="news", status="SUCCESS",
    result={"message": "[COMPANY] 정산 주기 단축 발표\nJD의 결제 시스템 개발 경험과 관련됩니다."},
    evidence=[evidence("news:a1", "news")],
)
FAILED = AgentResult(agent="position", status="FAILED", error="down")


def output(**overrides):
    base = {
        "answer": "지원 동기는 회사 방향과 연결되지만 공고의 기술 요구에 대한 근거가 비어 있습니다.",
        "judgments": [{
            "claim": "공고는 Spring API 개발을 요구하는데 자소서에는 그 근거가 없고, 뉴스가 보여 주는 정산 주기 단축 사업과 연결할 수 있는 경험을 앞세우면 두 공백을 한 번에 메울 수 있습니다.",
            "agents": ["jd", "news"],
            "evidence_ids": ["jd:ctx1", "news:a1"],
        }],
        "conflicts": [],
        "next_action": "2번 문항 첫 단락에 정산 배치 개선 경험을 Spring 기술명과 함께 한 문장 추가합니다.",
    }
    base.update(overrides)
    return base


class ValidateAggregateTest(unittest.TestCase):
    def test_accepts_judgment_that_links_two_agents_with_known_evidence(self):
        parsed = validate_aggregate(output(), [JD, NEWS, FAILED])
        self.assertEqual(parsed.judgments[0].agents, ["jd", "news"])

    def test_rejects_unknown_agent_and_failed_agent(self):
        bad = output(judgments=[{**output()["judgments"][0], "agents": ["jd", "position"]}])
        with self.assertRaises(AggregateOutputError) as raised:
            validate_aggregate(bad, [JD, NEWS, FAILED])
        self.assertIn("성공한 담당이 아닌", str(raised.exception))

    def test_rejects_evidence_id_not_in_results(self):
        bad = output(judgments=[{**output()["judgments"][0], "evidence_ids": ["news:zzz"]}])
        with self.assertRaises(AggregateOutputError) as raised:
            validate_aggregate(bad, [JD, NEWS])
        self.assertIn("근거 목록에 없는", str(raised.exception))

    def test_rejects_claim_copied_from_agent_message(self):
        parrot = output(judgments=[
            {"claim": "Spring 기반 API 개발 요구사항에 대한 근거가 자소서에 없습니다. 그래서 보완이 필요합니다.",
             "agents": ["jd", "news"], "evidence_ids": []},
        ])
        with self.assertRaises(AggregateOutputError) as raised:
            validate_aggregate(parrot, [JD, NEWS])
        self.assertIn("그대로 옮겼다", str(raised.exception))

    def test_requires_a_cross_agent_judgment_when_two_agents_succeeded(self):
        single = output(judgments=[
            {"claim": "공고 요구와 자소서 근거 사이에 큰 간격이 있어 보완이 우선입니다.", "agents": ["jd"], "evidence_ids": []},
        ])
        with self.assertRaises(AggregateOutputError) as raised:
            validate_aggregate(single, [JD, NEWS])
        self.assertIn("둘 이상을 엮은 판단이 없다", str(raised.exception))
        # 성공한 담당이 하나뿐이면 같은 출력이 통과한다
        validate_aggregate(single, [JD, FAILED])

    def test_available_evidence_ids_are_deduplicated_in_order(self):
        twice = AgentResult(agent="jd", status="SUCCESS", result={}, evidence=[evidence("jd:ctx1", "jd")])
        self.assertEqual(available_evidence_ids([JD, twice, NEWS]), ["jd:ctx1", "news:a1"])


class RenderAggregateTest(unittest.TestCase):
    def test_renders_four_sections_with_agent_labels(self):
        parsed = validate_aggregate(output(conflicts=[{
            "topic": "트래픽 경험 표현", "decision": "주장 대신 학습 방향으로 표현",
            "reason": "공고 분석은 근거 없음으로 보았고 다른 담당도 반대 근거를 내지 않았다",
        }]), [JD, NEWS])

        text = render_aggregate(parsed)

        self.assertTrue(text.startswith("지원 동기는"))
        self.assertIn("■ 종합 판단\n1. 공고는 Spring", text)
        self.assertIn("[채용공고·뉴스]", text)
        self.assertIn("■ 담당 간 의견 차이\n- 트래픽 경험 표현: 주장 대신", text)
        self.assertTrue(text.endswith("■ 다음에 할 일\n2번 문항 첫 단락에 정산 배치 개선 경험을 Spring 기술명과 함께 한 문장 추가합니다."))

    def test_omits_conflict_section_when_empty(self):
        self.assertNotIn("의견 차이", render_aggregate(validate_aggregate(output(), [JD, NEWS])))
