"""회사명 → corp_code 매핑. 추정으로 붙이지 않는 것이 요점이다."""
from __future__ import annotations

import unittest

from pipeline.news import corpmap


def _map(rows):
    return corpmap.CorpMap([dict(corp_code=c, corp_name=n, dart_corp_name=d)
                            for c, n, d in rows])


class NormalizeTest(unittest.TestCase):

    def test_법인표기와_기호를_지운다(self):
        self.assertEqual(corpmap.normalize_name("삼성전자(주)"), corpmap.normalize_name("삼성전자"))
        self.assertEqual(corpmap.normalize_name("주식회사 카카오"), corpmap.normalize_name("카카오"))
        self.assertEqual(corpmap.normalize_name("NAVER"), corpmap.normalize_name("naver"))

    def test_음차표기는_같아지지_않는다(self):
        # 사전 없이 맞추려면 추정이 필요하다. 일부러 붙이지 않는다.
        self.assertNotEqual(corpmap.normalize_name("SK하이닉스"),
                            corpmap.normalize_name("에스케이하이닉스"))


class ResolveTest(unittest.TestCase):

    def setUp(self):
        self.mapper = _map([
            ("00126380", "삼성전자", "삼성전자(주)"),
            ("00164779", "SK하이닉스", "에스케이하이닉스(주)"),
            ("01111111", "같은이름", "같은이름(주)"),
            ("02222222", "같은이름", "다른등록명(주)"),
        ])

    def test_정확일치(self):
        result = self.mapper.resolve("삼성전자")
        self.assertEqual((result.corp_code, result.method), ("00126380", "exact_name"))

    def test_등록명_정확일치(self):
        self.assertEqual(self.mapper.resolve("에스케이하이닉스(주)").corp_code, "00164779")

    def test_표기정규화_일치(self):
        result = self.mapper.resolve(" 삼성전자 ㈜ ")
        self.assertEqual(result.corp_code, "00126380")
        self.assertEqual(result.method, "normalized_name")

    def test_동명이인은_실패로_둔다(self):
        result = self.mapper.resolve("같은이름")
        self.assertEqual(result.corp_code, "")
        self.assertTrue(result.reason.startswith("ambiguous_name"))

    def test_없는_이름은_사유를_남긴다(self):
        result = self.mapper.resolve("존재하지않는회사")
        self.assertEqual(result.corp_code, "")
        self.assertEqual(result.reason, "not_in_company_universe")

    def test_부분일치로_붙이지_않는다(self):
        # '삼성' 은 '삼성전자' 에 붙지 않는다. 붙으면 삼성전기·삼성SDI 와 구분이 없다.
        self.assertEqual(self.mapper.resolve("삼성").corp_code, "")

    def test_빈_검색어(self):
        self.assertEqual(self.mapper.resolve("").reason, "empty_query_company_name")


class UniverseTest(unittest.TestCase):

    def test_실제_기업_마스터_원천을_읽는다(self):
        mapper = corpmap.load()
        self.assertGreater(mapper.row_count, 3000)
        self.assertEqual(mapper.resolve("삼성전자").corp_code, "00126380")


if __name__ == "__main__":
    unittest.main()
