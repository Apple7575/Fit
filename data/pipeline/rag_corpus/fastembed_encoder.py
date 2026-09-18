from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


def available_providers() -> list[str]:
    import onnxruntime as ort

    return ort.get_available_providers()


def preload_cuda_libraries() -> None:
    import onnxruntime as ort

    ort.preload_dlls(directory="")


def _text_embedding_factory(**kwargs: Any):
    from fastembed import TextEmbedding

    return TextEmbedding(**kwargs)


def _session_providers(model: Any) -> list[str]:
    current = model
    for _ in range(4):
        getter = getattr(current, "get_providers", None)
        if callable(getter):
            return list(getter())
        current = getattr(current, "model", None)
        if current is None:
            break
    return []


class FastEmbedEncoder:
    def __init__(
        self,
        model_name: str,
        *,
        device: str = "auto",
        cache_dir: str | None = None,
        model_factory: Callable[..., Any] = _text_embedding_factory,
    ):
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        if device == "cuda":
            preload_cuda_libraries()
        providers = available_providers()
        if device == "cuda" and "CUDAExecutionProvider" not in providers:
            raise RuntimeError("CUDAExecutionProvider is not available")
        resolved = "cuda" if device == "cuda" or (
            device == "auto" and "CUDAExecutionProvider" in providers
        ) else "cpu"
        selected_provider = "CUDAExecutionProvider" if resolved == "cuda" else "CPUExecutionProvider"
        self.model_name = model_name
        self._model = model_factory(
            model_name=model_name,
            cache_dir=cache_dir,
            providers=[selected_provider],
            cuda=False,
        )
        active_providers = _session_providers(self._model)
        if resolved == "cuda" and "CUDAExecutionProvider" not in active_providers:
            if device == "cuda":
                raise RuntimeError("CUDA session fell back to CPUExecutionProvider")
            resolved = "cpu"
        self.device = resolved

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.asarray(list(self._model.passage_embed(texts)), dtype=np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return np.asarray(list(self._model.query_embed(texts)), dtype=np.float32)
