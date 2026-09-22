"""벡터 저장 정밀도.

벡터가 코퍼스 용량의 대부분이라(2,640개사에서 84GB 중 60GB) 차원당 4바이트를 2바이트로
줄이면 절반이 된다. 저장 전에 단위 벡터로 정규화해 값이 좁은 범위(-0.2~0.2)에 모이므로
float16 으로도 검색 결과가 바뀌지 않는다 — 실측에서 상위 8건 일치율 100%.
"""
from __future__ import annotations

import unittest

import numpy as np

from pipeline.rag_corpus.embedding_build import DEFAULT_DTYPE, encode_vector


class EncodeVectorDtypeTest(unittest.TestCase):
    VECTOR = np.array([0.5, -0.25, 0.125, 0.0625], dtype=np.float32)

    def test_float32_is_the_default(self):
        self.assertEqual(DEFAULT_DTYPE, "float32")
        self.assertEqual(len(encode_vector(self.VECTOR)), 4 * 4)

    def test_float16_halves_the_stored_size(self):
        self.assertEqual(len(encode_vector(self.VECTOR, "float16")), 4 * 2)

    def test_both_precisions_store_the_same_unit_vector(self):
        """정규화는 정밀도와 무관하다. 길이가 1 이어야 코사인 유사도가 내적으로 계산된다."""
        for dtype, code in (("float32", "<f4"), ("float16", "<f2")):
            with self.subTest(dtype=dtype):
                stored = np.frombuffer(encode_vector(self.VECTOR, dtype), dtype=code)
                self.assertAlmostEqual(float(np.linalg.norm(stored)), 1.0, places=3)

    def test_float16_keeps_the_direction(self):
        """방향이 유지되어야 검색 순위가 바뀌지 않는다."""
        full = np.frombuffer(encode_vector(self.VECTOR, "float32"), dtype="<f4")
        half = np.frombuffer(encode_vector(self.VECTOR, "float16"), dtype="<f2").astype("<f4")

        self.assertGreater(float(full @ half), 0.9999)

    def test_unknown_dtype_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_vector(self.VECTOR, "float8")

    def test_zero_vector_is_still_rejected(self):
        with self.assertRaises(ValueError):
            encode_vector(np.zeros(4, dtype=np.float32), "float16")


if __name__ == "__main__":
    unittest.main()
