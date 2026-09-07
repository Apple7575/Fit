"""예측 누락과 보류를 성공으로 잘못 집계하지 않는지 검증한다."""
import unittest
from data.news_poc.pipeline.metrics import summarize_predictions

class MetricsTests(unittest.TestCase):
    def test_missing_predictions_cannot_silently_improve_score(self):
        with self.assertRaises(ValueError):
            summarize_predictions(['related','unrelated'],['related'])


    def test_abstention_is_counted_as_missed_related(self):
        metrics=summarize_predictions(['related','unrelated','uncertain'],['uncertain','related','uncertain'])
        self.assertEqual(metrics['missed_related'],1)
        self.assertEqual(metrics['false_related'],1)
        self.assertEqual(metrics['uncertain_correct'],1)
