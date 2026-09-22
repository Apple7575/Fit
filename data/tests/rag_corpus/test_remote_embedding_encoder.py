import unittest

import numpy as np

from pipeline.rag_corpus.remote_embedding_encoder import RemoteEmbeddingEncoder


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("remote secret")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class RemoteEmbeddingEncoderTests(unittest.TestCase):
    def test_passage_request_uses_openai_embeddings_path_model_and_bearer_key(self):
        session = FakeSession(FakeResponse({
            "data": [
                {"index": 1, "embedding": [3.0, 4.0]},
                {"index": 0, "embedding": [1.0, 2.0]},
            ]
        }))
        encoder = RemoteEmbeddingEncoder(
            "e5", base_url="http://gpu:8001/v1/", api_key="key",
            served_model_name="main-embedding", session=session,
        )

        vectors = encoder.embed_passages(["a", "b"])

        self.assertEqual(vectors.dtype, np.float32)
        self.assertEqual(vectors.shape, (2, 2))
        url, options = session.calls[0]
        self.assertEqual(url, "http://gpu:8001/v1/embeddings")
        self.assertEqual(options["headers"]["Authorization"], "Bearer key")
        self.assertEqual(options["json"], {
            "model": "main-embedding", "input": ["a", "b"],
            "encoding_format": "float",
        })

    def test_query_request_uses_query_input_type(self):
        session = FakeSession(FakeResponse({
            "data": [{"index": 0, "embedding": [1.0, 2.0]}]
        }))
        encoder = RemoteEmbeddingEncoder(
            "e5", base_url="http://gpu:8001", api_key="key", session=session,
        )

        encoder.embed_queries(["q"])

        sent = session.calls[0][1]["json"]["input"][0]
        self.assertEqual(
            sent,
            "Instruct: 주어진 기업 분석 질문과 관련된 한국 기업 공식 자료 근거를 검색하라\nQuery:q",
        )

    def test_rejects_wrong_model_dimension_and_vector_count(self):
        payloads = (
            {"data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}]},
            {"data": []},
            {"data": [{"index": 1, "embedding": [1.0] * 1024}]},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                encoder = RemoteEmbeddingEncoder(
                    "Qwen/Qwen3-Embedding-0.6B", base_url="http://gpu:8001", api_key="key",
                    session=FakeSession(FakeResponse(payload)),
                )
                with self.assertRaises(RuntimeError):
                    encoder.embed_passages(["a"])

    def test_requires_url_and_key(self):
        for url, key in (("", "key"), ("http://gpu:8001", "")):
            with self.subTest(url=url, key=key):
                with self.assertRaises(ValueError):
                    RemoteEmbeddingEncoder("e5", base_url=url, api_key=key)
