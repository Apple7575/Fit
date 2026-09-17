import unittest

from pipeline.raw_sources.chunking_profiles import get_chunking_profile


class ChunkingProfilesTest(unittest.TestCase):
    def test_exposes_three_versioned_experiment_profiles(self):
        compact = get_chunking_profile("structural-800-v1")
        baseline = get_chunking_profile("structural-1500-v2")
        adaptive = get_chunking_profile("adaptive-v1")

        self.assertEqual((compact.text_max_chars, compact.table_max_chars), (800, 800))
        self.assertEqual((baseline.text_max_chars, baseline.table_max_chars), (1500, 1500))
        self.assertEqual((adaptive.text_max_chars, adaptive.table_max_chars), (1200, 800))

    def test_rejects_unknown_profile(self):
        with self.assertRaisesRegex(ValueError, "지원하지 않는 청킹 프로필"):
            get_chunking_profile("unknown")
