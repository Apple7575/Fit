from __future__ import annotations

from typing import Any

import numpy as np
import requests

from .embedding_build import KNOWN_DIMENSIONS


QUERY_INSTRUCTION = "주어진 기업 분석 질문과 관련된 한국 기업 공식 자료 근거를 검색하라"


class RemoteEmbeddingEncoder:
    def __init__(
        self,
        model_name: str,
        *,
        base_url: str,
        api_key: str,
        served_model_name: str = "main",
        timeout: int = 180,
        session: Any | None = None,
    ):
        if not base_url.strip() or not api_key.strip() or not served_model_name.strip():
            raise ValueError("remote embedding URL, API key and served model are required")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.served_model_name = served_model_name
        self.timeout = timeout
        self.session = session or requests.Session()

    def _embed(self, texts: list[str]) -> np.ndarray:
        endpoint = (
            f"{self.base_url}/embeddings"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/embeddings"
        )
        response = self.session.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.served_model_name,
                "input": texts,
                "encoding_format": "float",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError("remote embedding vector count does not match")
        if any(not isinstance(item, dict) for item in data):
            raise RuntimeError("remote embedding response is invalid")
        indices = [item.get("index") for item in data]
        if sorted(indices) != list(range(len(texts))):
            raise RuntimeError("remote embedding indices do not match")
        ordered = sorted(data, key=lambda item: item["index"])
        vectors = np.asarray([item.get("embedding") for item in ordered], dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(texts):
            raise RuntimeError("remote embedding vector count does not match")
        expected_dimension = KNOWN_DIMENSIONS.get(self.model_name)
        if expected_dimension is not None and vectors.shape[1] != expected_dimension:
            raise RuntimeError("remote embedding dimension does not match")
        return vectors

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        instructed = [
            f"Instruct: {QUERY_INSTRUCTION}\nQuery:{text}" for text in texts
        ]
        return self._embed(instructed)
