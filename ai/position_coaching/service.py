import copy
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ai.jd_coaching.baseline import call_qwen
from ai.position_coaching.contracts import (
    load_experience_rubric,
    validate_documents,
    validate_experience_analysis_output,
)
from ai.position_coaching.prompt import build_position_messages


RESOURCE_ROOT = Path(__file__).parent / "resources"
RUBRIC_PATH = RESOURCE_ROOT / "rubrics" / "experience-depth-v1.json"
SCHEMA_PATH = RESOURCE_ROOT / "schemas" / "position-analysis-v2.json"
PROMPT_VERSION = "experience-depth-v2"
# 2026-09-22 실측: 모델 서버 생성 속도가 약 34토큰/초라 finding 2개(약 1,500토큰)에 45초쯤 걸린다.
# 총괄은 분석 담당들을 병렬로 돌리므로 90초까지는 Spring 제한 120초 안에 글쓰기까지 끝난다.
QWEN_TIMEOUT_SECONDS = 90
MAX_FINDINGS = 2
# 실측(2026-09-22): present_elements 인용이 출력의 70%를 차지해 finding 3개에 3,400토큰·100초가 걸렸다.
# 인용 길이를 스키마로 묶어 900토큰 안쪽을 목표로 한다.
MAX_CLAIM_QUOTE_CHARS = 200
MAX_ELEMENT_QUOTE_CHARS = 80

QwenCaller = Callable[..., dict[str, Any]]


class PositionAnalysisService:
    def __init__(
        self,
        config: Mapping[str, str],
        qwen_caller: QwenCaller = call_qwen,
    ) -> None:
        self._config = dict(config)
        self._qwen_caller = qwen_caller

    def analyze(
        self,
        rubric_id: str,
        position_context: Mapping[str, Any],
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
        instruction: str | None = None,
    ) -> dict[str, Any]:
        if rubric_id != "experience-depth-v1":
            raise ValueError("unsupported rubric_id")

        validated_documents = validate_documents(documents)
        rubric = load_experience_rubric(RUBRIC_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        if not any(document["text"].strip() for document in validated_documents):
            # 읽을 문서가 없으면 모델을 부르지 않는다. "경험 없음"은 코드가 결정한다.
            return validate_experience_analysis_output(
                _empty_analysis(rubric, self._config["model"]), validated_documents, rubric
            )
        model_schema = build_model_schema(schema)
        messages = build_position_messages(
            rubric,
            position_context,
            validated_documents,
            conversation,
            instruction,
        )

        for attempt in range(2):
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    timeout_seconds=QWEN_TIMEOUT_SECONDS,
                    schema=model_schema,
                    schema_name="position_analysis_v2_model",
                )
                output = complete_model_output(
                    copy.deepcopy(response["output"]), validated_documents, rubric
                )
                output["model_metadata"] = {
                    "base_model": response.get("model", self._config["model"]),
                    "base_revision": "deployment-alias-unresolved",
                    "adapter": None,
                    "training_dataset": None,
                    "prompt_version": PROMPT_VERSION,
                }
                return validate_experience_analysis_output(
                    output,
                    validated_documents,
                    rubric,
                )
            except (KeyError, TypeError, ValueError) as error:
                if attempt == 1:
                    raise RuntimeError("position analysis validation failed") from error
                messages.append({
                    "role": "user",
                    "content": f"검증 오류를 수정해 전체 JSON을 다시 반환하라: {error}",
                })

        raise RuntimeError("position analysis validation failed")


def build_model_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """모델에게 보낼 스키마. 저장 스키마(position-analysis-v2.json)에서 코드 소유 필드를 뺀다.

    1. 빈 결과 탈출구. 문서가 있는데도 모델이 NO_EXPERIENCE_CLAIM + findings [] 라는 가장 짧은
       유효 출력으로 빠져나가는 일이 실측에서 매번 재현됐다(프롬프트 지시로는 막히지 않음).
       상태는 COMPLETED 만, findings 는 1개 이상으로 고정한다.
    2. rubric·model_metadata. 코드가 채우는 값이라 모델이 만들 이유가 없다.
    3. claim 의 start_offset·end_offset. 모델의 위치 계산은 자주 틀리고 검증도 결국
       text.find 로 다시 찾는다. quote 만 받고 위치는 코드가 잡는다.
    4. missing_elements·verdict. present_elements 와 루브릭으로 값이 정해지므로 모델이 만들면
       중복 요소나 누락 때문에 서로 모순될 수 있다. 코드는 근거 요소만 받아 두 값을 계산한다.
    """
    model_schema = copy.deepcopy(dict(schema))
    model_schema["required"] = ["analysis_status", "findings"]
    model_schema["properties"].pop("rubric", None)
    model_schema["properties"].pop("model_metadata", None)
    model_schema["properties"]["analysis_status"]["enum"] = ["COMPLETED"]
    findings = model_schema["properties"]["findings"]
    findings["minItems"] = 1
    findings["maxItems"] = MAX_FINDINGS
    claim = findings["items"]["properties"]["claim"]
    claim["required"] = ["quote", "document_id"]
    claim["properties"].pop("start_offset", None)
    claim["properties"].pop("end_offset", None)
    claim["properties"]["quote"]["maxLength"] = MAX_CLAIM_QUOTE_CHARS
    finding = findings["items"]
    finding["required"] = [
        field for field in finding["required"]
        if field not in {"missing_elements", "verdict"}
    ]
    finding["properties"].pop("missing_elements", None)
    finding["properties"].pop("verdict", None)
    element_quote = findings["items"]["properties"]["present_elements"]["items"]["properties"]["quote"]
    element_quote["maxLength"] = MAX_ELEMENT_QUOTE_CHARS
    return model_schema


def complete_model_output(
    output: dict[str, Any],
    documents: Sequence[Mapping[str, str]],
    rubric: Mapping[str, Any],
) -> dict[str, Any]:
    """모델 응답의 코드 소유 필드를 채워 저장 스키마 모양으로 맞춘다."""
    output.setdefault("rubric", {"id": rubric["rubric_id"], "version": rubric["version"]})
    texts = {document["document_id"]: document["text"] for document in documents}
    required_by_claim_type = {
        item["code"]: item["required_elements"] for item in rubric.get("claim_types", [])
    }
    for finding in output.get("findings") or []:
        required = required_by_claim_type.get(finding.get("claim_type"))
        present_elements = finding.get("present_elements")
        if required is not None and isinstance(present_elements, list):
            normalized_present = []
            seen = set()
            for item in present_elements:
                if not isinstance(item, Mapping):
                    normalized_present.append(item)
                    continue
                element = item.get("element")
                if element not in required or element in seen:
                    continue
                seen.add(element)
                normalized_present.append(item)
            finding["present_elements"] = normalized_present
            finding["missing_elements"] = [
                element for element in required if element not in seen
            ]
            finding["verdict"] = (
                "SUFFICIENT"
                if len(seen) == len(required)
                else "PARTIAL"
                if "ACTION" in seen
                else "CLAIM_ONLY"
            )
            if finding["verdict"] == "SUFFICIENT":
                finding["follow_up_questions"] = []
        claim = finding.get("claim")
        if not isinstance(claim, dict) or "start_offset" in claim:
            continue
        text = texts.get(claim.get("document_id"), "")
        quote = claim.get("quote", "")
        start = text.find(quote) if isinstance(quote, str) and quote else -1
        # 못 찾으면 0,0 을 두어 검증이 "claim offset does not match quote" 로 거절하고 재시도하게 한다.
        claim["start_offset"] = max(start, 0)
        claim["end_offset"] = start + len(quote) if start >= 0 else 0
    return output


def _empty_analysis(rubric: Mapping[str, Any], model: str) -> dict[str, Any]:
    return {
        "analysis_status": "NO_EXPERIENCE_CLAIM",
        "rubric": {"id": rubric["rubric_id"], "version": rubric["version"]},
        "findings": [],
        "model_metadata": {
            "base_model": model,
            "base_revision": "deployment-alias-unresolved",
            "adapter": None,
            "training_dataset": None,
            "prompt_version": PROMPT_VERSION,
        },
    }

