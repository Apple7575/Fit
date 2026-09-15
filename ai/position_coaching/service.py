import copy
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ai.jd_coaching.baseline import call_qwen
from ai.position_coaching.contracts import (
    load_position_profile,
    validate_analysis_output,
    validate_documents,
)
from ai.position_coaching.prompt import build_position_messages


RESOURCE_ROOT = Path(__file__).parent / "resources"
PROFILE_PATH = RESOURCE_ROOT / "profiles" / "backend-v1.json"
SCHEMA_PATH = RESOURCE_ROOT / "schemas" / "position-analysis-v1.json"
PROMPT_VERSION = "position-depth-v1"
QWEN_TIMEOUT_SECONDS = 25

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
        position_profile_id: str,
        documents: Sequence[Mapping[str, Any]],
        conversation: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if position_profile_id != "backend-v1":
            raise ValueError("unsupported position_profile_id")

        validated_documents = validate_documents(documents)
        profile = load_position_profile(PROFILE_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        messages = build_position_messages(profile, validated_documents, conversation)

        for attempt in range(2):
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    timeout_seconds=QWEN_TIMEOUT_SECONDS,
                    schema=schema,
                    schema_name="position_analysis_v1",
                )
                output = copy.deepcopy(response["output"])
                output["model_metadata"] = {
                    "base_model": response.get("model", self._config["model"]),
                    "base_revision": "deployment-alias-unresolved",
                    "adapter": None,
                    "training_dataset": None,
                    "prompt_version": PROMPT_VERSION,
                }
                return validate_analysis_output(output, validated_documents, profile)
            except (KeyError, TypeError, ValueError) as error:
                if attempt == 1:
                    raise RuntimeError("position analysis validation failed") from error
                messages.append({
                    "role": "user",
                    "content": f"검증 오류를 수정해 전체 JSON을 다시 반환하라: {error}",
                })

        raise RuntimeError("position analysis validation failed")
