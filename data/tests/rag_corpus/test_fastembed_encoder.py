import unittest
from unittest.mock import patch

import numpy as np

from pipeline.rag_corpus.fastembed_encoder import FastEmbedEncoder


class FakeSession:
    def __init__(self, providers):
        self.providers = providers

    def get_providers(self):
        return self.providers


class FakeModel:
    def __init__(self, providers=("CPUExecutionProvider",)):
        self.model = FakeSession(list(providers))

    def passage_embed(self, texts):
        return [np.array([1.0, 2.0], dtype=np.float32) for _ in texts]

    def query_embed(self, texts):
        return [np.array([2.0, 1.0], dtype=np.float32) for _ in texts]


class FastEmbedEncoderTest(unittest.TestCase):
    def test_cuda_requires_the_cuda_execution_provider(self):
        with patch(
            "pipeline.rag_corpus.fastembed_encoder.available_providers",
            return_value=["CPUExecutionProvider"],
        ):
            with self.assertRaisesRegex(RuntimeError, "CUDAExecutionProvider"):
                FastEmbedEncoder("model", device="cuda", model_factory=lambda **kwargs: FakeModel())

    def test_cuda_is_passed_as_the_only_execution_provider(self):
        received = {}

        def factory(**kwargs):
            received.update(kwargs)
            return FakeModel(["CUDAExecutionProvider"])

        with patch(
            "pipeline.rag_corpus.fastembed_encoder.available_providers",
            return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
        ), patch(
            "pipeline.rag_corpus.fastembed_encoder.preload_cuda_libraries"
        ) as preload:
            encoder = FastEmbedEncoder("model", device="cuda", model_factory=factory)

        preload.assert_called_once_with()
        self.assertEqual(received["providers"], ["CUDAExecutionProvider"])
        self.assertEqual(received["cuda"], False)
        self.assertEqual(encoder.device, "cuda")

    def test_cuda_rejects_a_session_that_silently_fell_back_to_cpu(self):
        with patch(
            "pipeline.rag_corpus.fastembed_encoder.available_providers",
            return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
        ):
            with self.assertRaisesRegex(RuntimeError, "fell back"):
                FastEmbedEncoder(
                    "model", device="cuda",
                    model_factory=lambda **kwargs: FakeModel(["CPUExecutionProvider"]),
                )

    def test_cpu_is_explicit_and_embedding_results_are_arrays(self):
        received = {}

        def factory(**kwargs):
            received.update(kwargs)
            return FakeModel()

        encoder = FastEmbedEncoder("model", device="cpu", model_factory=factory)

        self.assertEqual(received["providers"], ["CPUExecutionProvider"])
        self.assertEqual(received["cuda"], False)
        self.assertEqual(encoder.embed_passages(["a", "b"]).shape, (2, 2))
        self.assertEqual(encoder.embed_queries(["q"]).shape, (1, 2))

    def test_rejects_unknown_device_before_model_construction(self):
        with self.assertRaisesRegex(ValueError, "device"):
            FastEmbedEncoder("model", device="tpu", model_factory=lambda **kwargs: FakeModel())
