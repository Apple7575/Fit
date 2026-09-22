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
PROMPT_VERSION = "experience-depth-v1"
# 실측 생성 시간이 약 25초(완성 토큰 800여 개)라 25초 제한은 절반쯤 타임아웃 났다.
# 백엔드 총괄 제한 120초 안에서 검증 실패 재시도 한 번까지 들어가는 값이다.
QWEN_TIMEOUT_SECONDS = 45

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
                    schema=schema,
                    schema_name="position_analysis_v2",
                )
                output = copy.deepcopy(response["output"])
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
