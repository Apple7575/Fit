from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

DATA = Path(__file__).resolve().parents[2]
SCRIPTS = DATA / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_rag_corpus
from pipeline.rag_corpus.load import BuildResult
from pipeline.rag_corpus.source import CompanySourceRows


FIRST = "00126380"
SECOND = "00164779"


class Cursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))

    def fetchall(self):
        return [(code,) for code in self.conn.company_codes]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, company_codes):
        self.company_codes = company_codes
        self.queries = []
        self.replacements = []
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return Cursor(self)


class ConnectionFactory:
    def __init__(self, company_codes):
        self.company_codes = company_codes
        self.connections = []

    def __call__(self):
        conn = Connection(self.company_codes)
        self.connections.append(conn)
        return Transaction(conn)


class Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.conn.committed = True
        else:
            self.conn.rolled_back = True
        return False


def rows(corp_code):
    return CompanySourceRows(
        profile={"corp_code": corp_code}, metrics=[], texts=[], segments=[], activities=[])


def result(corp_code):
    return BuildResult(
        records=[],
        input_counts={"profile": 1, "metrics": 0, "texts": 0, "segments": 0, "activities": 0},
        excluded_counts={},
    )


class BuildRagCorpusCliTest(unittest.TestCase):
    # 이 테스트가 막는 결함: 전체 재구축에서 DB 반환 순서대로 처리해 결과가 비결정적이 되는 경우.
    def test_run_selects_every_company_in_sorted_order(self):
        factory = ConnectionFactory([SECOND, FIRST])
        built = []

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records",
                          side_effect=lambda source: built.append(source.profile["corp_code"]) or result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=lambda conn, code, _: conn.replacements.append(code)):
            summary = build_rag_corpus.run(factory, None, dry_run=False)

        self.assertEqual(built, [FIRST, SECOND])
        self.assertEqual(summary["company_count"], 2)
        self.assertEqual([conn.replacements for conn in factory.connections[1:]], [[FIRST], [SECOND]])

    # 이 테스트가 막는 결함: 반복된 옵션이 같은 기업을 두 번 지우고 다시 넣는 경우.
    def test_run_deduplicates_targeted_company_codes_preserving_first_request_order(self):
        factory = ConnectionFactory([FIRST, SECOND])
        built = []

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records",
                          side_effect=lambda source: built.append(source.profile["corp_code"]) or result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=lambda conn, code, _: conn.replacements.append(code)):
            build_rag_corpus.run(factory, [SECOND, FIRST, SECOND], dry_run=False)

        self.assertEqual(built, [SECOND, FIRST])
        self.assertEqual([conn.replacements for conn in factory.connections[1:]], [[SECOND], [FIRST]])

    # 이 테스트가 막는 결함: 존재하지 않는 코드를 첫 기업 교체 뒤에 발견해 이미 DB를 바꾸는 경우.
    def test_run_rejects_unknown_company_before_any_mutation(self):
        factory = ConnectionFactory([FIRST])

        with patch.object(build_rag_corpus, "replace_company") as replace:
            with self.assertRaisesRegex(ValueError, "기업을 찾을 수 없습니다: 99999999"):
                build_rag_corpus.run(factory, [FIRST, "99999999"], dry_run=False)

        self.assertFalse(replace.called)
        self.assertEqual(len(factory.connections), 1)

    # 이 테스트가 막는 결함: dry run이 기존 코퍼스를 삭제하거나 새 행을 삽입하는 경우.
    def test_run_dry_run_does_not_replace_any_company(self):
        factory = ConnectionFactory([FIRST])

        with patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source: result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company") as replace:
            summary = build_rag_corpus.run(factory, [FIRST], dry_run=True)

        self.assertEqual(summary["company_count"], 1)
        self.assertFalse(replace.called)
        self.assertTrue(factory.connections[1].committed)

    # 이 테스트가 막는 결함: 기업 교체 중 오류가 나도 예전 코퍼스가 삭제된 채로 커밋되는 경우.
    def test_main_returns_one_and_rolls_back_the_failing_company_transaction(self):
        factory = ConnectionFactory([FIRST])
        output = io.StringIO()

        with patch.object(build_rag_corpus, "connect", factory), \
             patch.object(build_rag_corpus, "load_company_source_rows", side_effect=lambda _, code: rows(code)), \
             patch.object(build_rag_corpus, "build_company_records", side_effect=lambda source: result(source.profile["corp_code"])), \
             patch.object(build_rag_corpus, "replace_company", side_effect=RuntimeError("insert failed")), \
             patch.object(sys, "argv", ["build_rag_corpus.py", "--corp-code", FIRST]), \
             redirect_stdout(output):
            exit_code = build_rag_corpus.main()

        self.assertEqual(exit_code, 1)
        self.assertTrue(factory.connections[1].rolled_back)
        self.assertFalse(factory.connections[1].committed)
        self.assertEqual(json.loads(output.getvalue()), {"status": "failed", "error": "insert failed"})


if __name__ == "__main__":
    unittest.main()
