"""공급자 선택과 설정 읽기."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai.llm.config import (
    ANTHROPIC,
    GMS,
    OPENAI,
    VLLM,
    load_llm_config,
    resolve_model,
    resolve_provider,
)


class ResolveProviderTest(unittest.TestCase):
    def test_defaults_to_vllm(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_provider({}), VLLM)

    def test_env_file_value_is_used(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_provider({"LLM_PROVIDER": "gms"}), GMS)

    def test_environment_wins_over_env_file(self):
        """컨테이너는 compose 로 주입한다. .env 는 개발 PC 용이다."""
        with patch.dict("os.environ", {"LLM_PROVIDER": "gms"}, clear=True):
            self.assertEqual(resolve_provider({"LLM_PROVIDER": "vllm"}), GMS)

    def test_agent_prefix_overrides_global(self):
        """한 담당씩 옮겨 보기 위한 자리."""
        with patch.dict("os.environ", {}, clear=True):
            values = {"LLM_PROVIDER": "vllm", "COMPANY_ANALYSIS_LLM_PROVIDER": "gms"}
            self.assertEqual(resolve_provider(values, prefix="COMPANY_ANALYSIS"), GMS)
            self.assertEqual(resolve_provider(values), VLLM)

    def test_unknown_provider_is_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                resolve_provider({"LLM_PROVIDER": "bedrock"})

    def test_agent_default_assignment_beats_global_provider(self):
        """dev·prod 는 LLM_PROVIDER=gms 로 전부 Gemini 에 몰렸다. 담당별 기본 배정이 그것을 나눈다."""
        with patch.dict("os.environ", {}, clear=True):
            values = {"LLM_PROVIDER": "gms"}
            self.assertEqual(resolve_provider(values, prefix="JD"), OPENAI)
            self.assertEqual(resolve_provider(values, prefix="SUPERVISOR_AGGREGATE"), ANTHROPIC)
            self.assertEqual(resolve_provider(values, prefix="WRITING"), GMS)
            # 기본 배정이 없는 접두사는 전역을 따른다.
            self.assertEqual(resolve_provider(values, prefix="INTERVIEW"), GMS)

    def test_agent_override_beats_default_assignment(self):
        with patch.dict("os.environ", {"JD_LLM_PROVIDER": "anthropic"}, clear=True):
            self.assertEqual(resolve_provider({}, prefix="JD"), ANTHROPIC)


class ResolveModelTest(unittest.TestCase):
    def test_default_assignment_model_when_provider_matches(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_model(OPENAI, {}, prefix="JD"), "gpt-4.1-mini")
            self.assertEqual(resolve_model(GMS, {}, prefix="WRITING"), "gemini-2.5-flash")

    def test_provider_default_when_assignment_provider_differs(self):
        """JD 를 Claude 로 돌리라고만 하면 모델은 Claude 기본값이다. gpt 이름을 Claude 에 보내지 않는다."""
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_model(ANTHROPIC, {}, prefix="JD"), "claude-haiku-4-5-20251001")

    def test_model_override_wins(self):
        with patch.dict("os.environ", {"WRITING_LLM_MODEL": "gemini-2.5-pro"}, clear=True):
            self.assertEqual(resolve_model(GMS, {}, prefix="WRITING"), "gemini-2.5-pro")

    def test_global_gms_model_still_applies_without_prefix(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_model(GMS, {"GMS_MODEL": "gemini-2.5-pro"}), "gemini-2.5-pro")
            self.assertEqual(resolve_model(GMS, {}), "gemini-2.5-flash-lite")


class LoadLlmConfigTest(unittest.TestCase):
    def test_loads_vllm_settings(self):
        path = self._env_file(
            "QWEN_BASE_URL=http://gpu:8000/v1/\nQWEN_MODEL=main\nQWEN_API_KEY=k\n"
        )
        with patch.dict("os.environ", {}, clear=True):
            config = load_llm_config(path)

        self.assertEqual(config.provider, VLLM)
        self.assertEqual(config.base_url, "http://gpu:8000/v1")  # 끝 슬래시는 떼어 둔다
        self.assertEqual(config.model, "main")

    def test_loads_gms_settings_with_defaults(self):
        path = self._env_file("LLM_PROVIDER=gms\nGMS_KEY=secret\n")
        with patch.dict("os.environ", {}, clear=True):
            config = load_llm_config(path)

        self.assertEqual(config.provider, GMS)
        self.assertEqual(config.base_url, "https://gms.ssafy.io/gmsapi")
        self.assertEqual(config.model, "gemini-2.5-flash-lite")
        self.assertEqual(config.api_key, "secret")

    def test_missing_gms_key_is_named(self):
        path = self._env_file("LLM_PROVIDER=gms\n")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GMS_KEY"):
                load_llm_config(path)

    def test_missing_vllm_settings_are_named(self):
        path = self._env_file("QWEN_MODEL=main\n")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "QWEN_BASE_URL"):
                load_llm_config(path)

    def _env_file(self, body: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
        handle.write(body)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return Path(handle.name)


if __name__ == "__main__":
    unittest.main()
