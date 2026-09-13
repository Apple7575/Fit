import unittest

from pipeline.rag_corpus.source import load_company_source_rows


CORP_CODE = "00126380"


class RecordingCursor:
    def __init__(self, result_sets):
        self.result_sets = result_sets
        self.executed = []
        self._current = []

    def execute(self, query, params):
        self.executed.append((query, params))
        index = len(self.executed) - 1
        self._current = self.result_sets[index] if index < len(self.result_sets) else []

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return self._current

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RecordingConnection:
    def __init__(self, result_sets):
        self.cursor_instance = RecordingCursor(result_sets)

    def cursor(self):
        return self.cursor_instance


class CompanySourceReaderTest(unittest.TestCase):
    def test_rejects_unknown_company_before_reading_other_canonical_sources(self):
        conn = RecordingConnection([[]])

        with self.assertRaisesRegex(ValueError, CORP_CODE):
            load_company_source_rows(conn, CORP_CODE)

        self.assertEqual(len(conn.cursor_instance.executed), 1)

    def test_queries_are_company_scoped_and_grouped_rows_are_deterministic(self):
        conn = RecordingConnection([
            [{"corp_code": CORP_CODE, "corp_name": "삼성전자"}],
            [{"metric_code": "revenue"}],
            [{"attr_key": "main_product", "seq": 2}, {"attr_key": "main_product", "seq": 1}],
            [{"segment_name": "DX", "metric_code": "z"}, {"segment_name": "DX", "metric_code": "a"}],
            [{"id": 2}, {"id": 1}],
        ])

        rows = load_company_source_rows(conn, CORP_CODE)

        self.assertEqual(rows.profile["corp_code"], CORP_CODE)
        self.assertEqual([row["metric_code"] for row in rows.metrics], ["revenue"])
        self.assertEqual(len(conn.cursor_instance.executed), 5)
        for query, params in conn.cursor_instance.executed:
            self.assertRegex(" ".join(query.lower().split()), r"where .*corp_code = %s")
            self.assertEqual(params, (CORP_CODE,))
        self.assertIn("order by ct.fiscal_year, ct.attr_key, ct.seq", " ".join(conn.cursor_instance.executed[2][0].lower().split()))
        self.assertIn("order by sm.fiscal_year, sm.segment_name, sm.metric_code", " ".join(conn.cursor_instance.executed[3][0].lower().split()))
        self.assertIn("order by ca.fiscal_year, ca.activity_type, ca.id", " ".join(conn.cursor_instance.executed[4][0].lower().split()))

    def test_metric_query_joins_catalog_and_evidence_on_full_company_year_metric_key(self):
        conn = RecordingConnection([[{"corp_code": CORP_CODE, "corp_name": "삼성전자"}], [], [], [], []])

        load_company_source_rows(conn, CORP_CODE)

        metric_query = " ".join(conn.cursor_instance.executed[1][0].lower().split())
        self.assertIn("join metric m on m.metric_code = cm.metric_code", metric_query)
        self.assertIn("left join metric_evidence me on me.corp_code = cm.corp_code and me.fiscal_year = cm.fiscal_year and me.metric_code = cm.metric_code", metric_query)


if __name__ == "__main__":
    unittest.main()
