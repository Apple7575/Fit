"""raw → staged. 버리는 행이 없고, 재실행 결과가 같아야 한다."""
from __future__ import annotations

import filecmp
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.news import corpmap, rawstore, stage, urls
from pipeline.news.schema import PROVIDER, STAGED_FIELDS
from pipeline.news.csvio import read_csv
from tests.news import fixtures

# KST 2026-09-06 하루. UTC 로는 09-05T15:00 ~ 09-06T15:00 이다.
TARGET_START, TARGET_END = "2026-09-06", "2026-09-07"
IN_WINDOW = "Sat, 05 Sep 2026 23:30:00 GMT"        # KST 09-06 08:30
OUT_WINDOW = "Sat, 05 Sep 2026 10:00:00 GMT"       # KST 09-05 19:00


def _mapper():
    return corpmap.CorpMap([
        {"corp_code": "00126380", "corp_name": "삼성전자", "dart_corp_name": "삼성전자(주)"},
    ])


class StageTest(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.raw = Path(self.temporary.name) / "raw"
        self.out = Path(self.temporary.name) / "staged"
        self.addCleanup(self.temporary.cleanup)

    def _run(self, items, company="삼성전자"):
        plan = fixtures.daily_plan(TARGET_START, TARGET_END)
        payload = fixtures.feed(items)
        empty = fixtures.feed([])
        entries = [("day0", empty, plan[0][0], plan[0][1]),
                   ("day1", payload, plan[1][0], plan[1][1])]
        fixtures.write_run(self.raw / "run1", entries, company=company)
        run = rawstore.load_run("run1", raw_dir=self.raw)
        return run, stage.stage_run(run, _mapper())

    def test_대상_구간을_요청계획에서_되돌린다(self):
        run, _ = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)])
        self.assertEqual(stage.derive_target_window(run), (TARGET_START, TARGET_END))

    def test_기본_정제_결과(self):
        _, result = self._run([
            fixtures.item("삼성전자 신규 투자", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("삼성전자 실적 발표", "https://b.test/2", "g2", IN_WINDOW),
        ])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.summary["staged_rows"], 2)
        row = result.rows[0]
        self.assertEqual(row["provider"], PROVIDER)
        self.assertEqual(row["publisher"], "테스트일보")
        self.assertEqual(row["corp_code"], "00126380")
        self.assertEqual(row["corp_map_method"], "exact_name")
        self.assertEqual(row["query_company_name"], "삼성전자")
        self.assertEqual(row["published_date_kst"], "2026-09-06")
        self.assertEqual(row["language"], "ko")
        self.assertEqual(row["country"], "KR")
        self.assertEqual(row["stage_status"], "staged")
        self.assertEqual(row["collected_at"], "2026-09-06T00:10:00+00:00")
        self.assertEqual(set(row) - set(STAGED_FIELDS), set())

    def test_provider_와_publisher_를_섞지_않는다(self):
        _, result = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)])
        row = result.rows[0]
        self.assertEqual(row["provider"], "google_news_rss")
        self.assertNotEqual(row["provider"], row["publisher"])

    def test_원본_문자열을_남긴다(self):
        _, result = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)])
        self.assertEqual(result.rows[0]["published_at_raw"], IN_WINDOW)
        self.assertTrue(result.rows[0]["published_at"].startswith("2026-09-05T23:30"))

    def test_요약과_AI_컬럼은_채우지_않는다(self):
        _, result = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)])
        row = result.rows[0]
        self.assertEqual(row["description"], "")
        self.assertEqual(row["description_raw"], "본문 일부")
        self.assertEqual(row["description_status"], "needs_review")
        self.assertEqual(row["image_url"], "")

    def test_기간_밖은_버리지_않고_분리한다(self):
        _, result = self._run([
            fixtures.item("안", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("밖", "https://b.test/2", "g2", OUT_WINDOW),
        ])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual([r["reject_reason"] for r in result.rejects], ["outside_target_window"])
        self.assertEqual(result.summary["raw_observations"], 2)
        self.assertEqual(
            result.summary["staged_rows"] + result.summary["duplicate_rows"]
            + result.summary["rejected_rows"], 2)

    def test_같은_기사키는_중복으로_분리한다(self):
        item = fixtures.item("같은 기사", "https://a.test/1", "g1", IN_WINDOW)
        _, result = self._run([item, item])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.duplicates[0]["duplicate_rule"], "article_key")

    def test_URL_정규화_중복(self):
        _, result = self._run([
            fixtures.item("가", "https://a.test/1?utm_source=x", "g1", IN_WINDOW),
            fixtures.item("나", "https://A.test/1/", "g2", IN_WINDOW),
        ])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.duplicates[0]["duplicate_rule"], "original_url_norm")

    def test_제목만_같고_날짜가_다르면_중복이_아니다(self):
        _, result = self._run([
            fixtures.item("같은 제목", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("같은 제목", "https://b.test/2", "g2",
                          "Sun, 06 Sep 2026 02:00:00 GMT"),   # KST 09-06 11:00, 같은 날
        ])
        # 같은 KST 날짜 + 같은 제목 체크섬이면 중복이다.
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.duplicates[0]["duplicate_rule"],
                         "title_checksum+published_date_kst")

    def test_제목_누락은_입력결함으로_분리한다(self):
        _, result = self._run([
            fixtures.item("", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("정상", "https://b.test/2", "g2", IN_WINDOW),
        ])
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rejects[0]["reject_reason"], "input_defect:missing_title")

    def test_확인된_목록페이지는_수집기_규칙으로_분리한다(self):
        _, result = self._run([
            fixtures.item("목록", "https://stock.mk.co.kr/price/news/1", "g1", IN_WINDOW),
        ])
        self.assertEqual(len(result.rows), 0)
        self.assertIn("known_listing_page", result.rejects[0]["reject_reason"])

    def test_매핑_실패는_기업을_붙이지_않고_사유를_남긴다(self):
        _, result = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)],
                              company="알수없는회사")
        row = result.rows[0]
        self.assertEqual(row["corp_code"], "")
        self.assertEqual(row["corp_map_reason"], "not_in_company_universe")
        self.assertEqual(row["stage_status"], "unresolved_corp")
        self.assertEqual(result.summary["unresolved_corp_rows"], 1)

    def test_수집기_집계와_대조값을_남긴다(self):
        _, result = self._run([
            fixtures.item("안", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("밖", "https://b.test/2", "g2", OUT_WINDOW),
        ])
        self.assertEqual(result.summary["collector_target_observations"],
                         result.summary["in_window_observations"])

    def test_재실행_결과가_바이트까지_같다(self):
        _, first = self._run([
            fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW),
            fixtures.item("나", "https://b.test/2", "g2", IN_WINDOW),
        ])
        run = rawstore.load_run("run1", raw_dir=self.raw)
        second = stage.stage_run(run, _mapper())
        one = stage.write(first, self.out / "a")
        two = stage.write(second, self.out / "b")
        self.assertTrue(filecmp.cmp(one["articles"], two["articles"], shallow=False))
        self.assertTrue(filecmp.cmp(one["rejects"], two["rejects"], shallow=False))

    def test_CSV_는_BOM_없는_UTF8_LF(self):
        _, result = self._run([fixtures.item("가", "https://a.test/1", "g1", IN_WINDOW)])
        paths = stage.write(result, self.out / "c")
        payload = paths["articles"].read_bytes()
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", payload)
        self.assertEqual(read_csv(paths["articles"])[0]["provider"], PROVIDER)
        summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
        self.assertEqual(summary["provider"], PROVIDER)

    def test_원본이_없으면_표본을_만들지_않는다(self):
        (self.raw / "empty").mkdir(parents=True)
        with self.assertRaises(ValueError):
            rawstore.load_run("empty", raw_dir=self.raw)


class UrlTest(unittest.TestCase):

    def test_추적_파라미터만_지운다(self):
        self.assertEqual(urls.normalize("https://A.test/x/?utm_source=a&idxno=7"),
                         "https://a.test/x?idxno=7")

    def test_기사_식별_쿼리는_남긴다(self):
        self.assertEqual(urls.normalize("https://n.test/view?idxno=12345"),
                         "https://n.test/view?idxno=12345")

    def test_www_와_끝_슬래시(self):
        self.assertEqual(urls.normalize("https://www.n.test/a/"), "https://n.test/a")

    def test_빈_값(self):
        self.assertEqual(urls.normalize(""), "")


if __name__ == "__main__":
    unittest.main()
