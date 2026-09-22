import unittest

from pipeline.rag_corpus.experiment_selection import select_companies


class ExperimentSelectionTest(unittest.TestCase):
    def test_selects_fixed_size_with_tuning_and_holdout_groups(self):
        companies = {
            f"{index:08d}": {
                "record_count": index + 1,
                "failures": [{"reason": "broken"}] if index % 17 == 0 else [],
            }
            for index in range(150)
        }

        first = select_companies(companies, size=100, holdout_size=20)
        second = select_companies(companies, size=100, holdout_size=20)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 100)
        self.assertEqual(len({item["corp_code"] for item in first}), 100)
        self.assertEqual(sum(item["group"] == "tuning" for item in first), 80)
        self.assertEqual(sum(item["group"] == "holdout" for item in first), 20)


if __name__ == "__main__":
    unittest.main()
