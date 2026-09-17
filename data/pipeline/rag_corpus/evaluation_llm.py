"""평가셋 초안 생성과 검증에 사용하는 OpenAI 호환 Qwen 호출."""

from __future__ import annotations

import json

import requests


GENERATOR_PROMPT_VERSION = "company-retrieval-generator-v5"
JUDGE_PROMPT_VERSION = "company-retrieval-judge-v1"


class QwenEvaluationClient:
    def __init__(self, base_url: str, model: str, api_key: str, *, session=None, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout

    def complete(self, system: str, user: str) -> dict[str, object]:
        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0, "max_tokens": 1200,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = json.loads(response.json()["choices"][0]["message"]["content"])
        if not isinstance(result, dict):
            raise ValueError("LLM 응답은 JSON 객체여야 합니다")
        return result

    def generate(self, category: str, units: list[dict[str, object]]) -> dict[str, object]:
        return self.complete(
            "사업보고서 검색 평가 질문 생성기다. 제공된 원문 밖의 사실은 쓰지 않는다. "
            "JSON 객체만 반환한다. section_index, kind, source_index는 선택한 한 근거 단위의 값을 "
            "변경 없이 복사한다. source_quote는 그 근거 단위 text에서 연속된 부분 문자열을 그대로 복사한다. "
            "질문과 답은 해당 기업의 실질적인 사실 하나를 직접 묻고 답해야 한다. "
            "시장 일반론이나 원문에 값이 없어 '명시되지 않았다'고 답하는 질문은 만들지 않는다. "
            "표 숫자에 % 표시가 없으면 비율의 단위를 퍼센트로 추정하지 않는다. "
            "표 머리글 단어를 답으로 복사하지 않는다. "
            "목차명이나 표 제목 자체를 묻지 않는다. 다른 문단이나 보고서 표지에서 연도와 회계 기준을 추론하지 않는다. "
            "질문·답·메타데이터의 연도, 연결·별도 기준, 비교 관계는 source_quote에 명시된 경우만 쓴다. "
            "answer의 모든 숫자는 source_quote 안에도 동일한 표기로 있어야 한다.",
            "다음 원문 근거에서 " + category + " 질문 하나를 만들어라. "
            "필드: question, answer, section_index, kind, source_index, source_quote, "
            "fiscal_year, unit, accounting_basis. 숫자 질문에는 연도·단위·연결/별도 기준을 명시한다. "
            "원문에 회계 기준이 없으면 accounting_basis는 UNSPECIFIED로 두고 질문에도 넣지 않는다. "
            "원문 근거 한 개만 선택하고, 답에 쓰는 숫자·연도·단위를 모두 포함하도록 인용하라. "
            "원문 근거: " + json.dumps(units, ensure_ascii=False),
        )

    def judge(self, candidate: dict[str, object], source: dict[str, object]) -> dict[str, object]:
        result = self.complete(
            "사업보고서 검색 평가 질문의 독립 검증자다. 원문 한 근거만으로 질문에 답할 수 있을 때만 "
            "supported를 true로 반환한다. 추론·단위 변환·외부 지식은 허용하지 않는다. JSON 객체만 반환한다.",
            "supported 불리언과 reason 문자열을 반환하라. 평가 후보: "
            + json.dumps(candidate, ensure_ascii=False) + " 원문 근거: "
            + json.dumps(source, ensure_ascii=False),
        )
        return {"supported": result.get("supported") is True, "reason": str(result.get("reason") or "")}
