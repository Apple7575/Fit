"""전 종목 수집 드라이버 — 계획·간격·중단 규칙을 고정한다.

네트워크는 타지 않는다. `fetch_fn`·`sleep_fn` 을 넣어 호출을 세는 방식이라
수집기(`news_poc/pipeline/collect.py`)의 시험 방식과 같다.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

DATA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATA))
sys.path.insert(0, str(DATA / "scripts"))

import collect_news  # noqa: E402

FEED = (b'<?xml version="1.0"?><rss version="2.0"><channel>'
        b'<item><title>\xea\xb8\xb0\xec\x82\xac</title>'
        b'<link>https://news.google.com/rss/articles/CBMiTEST</link>'
        b'<guid isPermaLink="false">CBMiTEST</guid>'
        b'<pubDate>Mon, 14 Sep 2026 01:00:00 GMT</pubDate>'
        b'<source url="https://example.com">\xec\x98\x88\xec\x8b\x9c</source>'
        b'</item></channel></rss>')

START, END = date(2026, 9, 14), date(2026, 9, 21)


class Recorder:
    """받은 URL 과 잠든 횟수를 센다."""

    def __init__(self, behaviour=None):
        self.urls: list[str] = []
        self.sleeps: list[float] = []
        self.behaviour = behaviour or (lambda url, n: (FEED, 200, url))

    def fetch(self, url):
        self.urls.append(url)
        return self.behaviour(url, len(self.urls))

    def sleep(self, seconds):
        self.sleeps.append(seconds)


class PlanTest(unittest.TestCase):
    def test_주_단위_창은_기업당_한_요청이다(self):
        plan = collect_news.build_plan(["삼성전자", "카카오"], START, END)
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["kind"], "weekly")

    def test_창은_시작_하루_전부터_건다(self):
        """`after:D-1 before:D` 가 KST 하루 D 라는 수집기 규칙을 따른다."""
        spec = collect_news.build_plan(["삼성전자"], START, END)[0]
        self.assertEqual(spec["query"], "삼성전자 after:2026-09-13 before:2026-09-21")
        self.assertIn("hl=ko", spec["url"])

    def test_하루_단위는_요청이_기업당_창_수만큼_난다(self):
        """옛 방식이다. 전 종목이면 26시간이라 기본값이 아니다."""
        weekly = collect_news.build_plan(["삼성전자"], START, END)
        daily = collect_news.build_plan(["삼성전자"], START, END, window="daily")
        self.assertEqual(len(weekly), 1)
        self.assertEqual(len(daily), 8)

    def test_시작이_끝보다_뒤면_거부한다(self):
        with self.assertRaises(ValueError):
            collect_news.build_plan(["삼성전자"], END, START)

    def test_상장사만_추린다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "universe.csv"
            path.write_text("corp_code,corp_name,corp_cls\n"
                            "1,상장사,Y\n2,코스닥,K\n3,기타법인,E\n",
                            encoding="utf-8-sig")
            names = collect_news.company_names(path, aliases=False)
        self.assertEqual(names, ["상장사", "코스닥"])

    def test_전_종목_목록이_2천개사_위다(self):
        """실제 유니버스로 한 번 본다 — 범위가 조용히 100개사로 돌아가지 않게."""
        names = collect_news.company_names()
        self.assertGreater(len(names), 2500, len(names))


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def run_plan(self, names, recorder, **kw):
        plan = collect_news.build_plan(names, START, END)
        return collect_news.run(plan, self.out, interval=5, fetch_fn=recorder.fetch,
                                sleep_fn=recorder.sleep, progress_every=0,
                                log=lambda *a: None, **kw)

    def test_요청_사이에만_기다린다(self):
        """세 요청이면 기다림은 둘이다. 첫 요청 앞에서 5초를 버리지 않는다."""
        rec = Recorder()
        summary = self.run_plan(["가", "나", "다"], rec)
        self.assertEqual(summary["ok"], 3)
        self.assertEqual(rec.sleeps, [5, 5])

    def test_이미_받은_것은_다시_요청하지_않는다(self):
        rec = Recorder()
        self.run_plan(["가", "나"], rec)
        again = Recorder()
        summary = self.run_plan(["가", "나"], again)
        self.assertEqual((summary["cached"], summary["ok"]), (2, 0))
        self.assertEqual(again.urls, [])
        self.assertEqual(again.sleeps, [])

    def test_받은_것은_requests_json_에_남는다(self):
        rec = Recorder()
        self.run_plan(["가"], rec)
        records = json.loads((self.out / "requests.json").read_text(encoding="utf-8"))
        (record,) = records.values()
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["count"], 1)
        self.assertIn("sha256", record)
        self.assertTrue((self.out / (record["id"] + ".xml")).exists())

    def test_4xx_면_거기서_멈춘다(self):
        """403·429 는 막혔다는 신호다. 남은 기업을 두드리지 않는다."""
        def behaviour(url, n):
            if n == 2:
                raise HTTPError(url, 429, "Too Many Requests", {}, None)
            return FEED, 200, url

        rec = Recorder(behaviour)
        summary = self.run_plan(["가", "나", "다", "라"], rec)
        self.assertEqual(len(rec.urls), 2)
        self.assertEqual(summary["ok"], 1)
        self.assertIn("나", summary["blocked_at"])

    def test_5xx_는_그_건만_실패로_적고_계속한다(self):
        def behaviour(url, n):
            if n == 1:
                raise HTTPError(url, 503, "Service Unavailable", {}, None)
            return FEED, 200, url

        rec = Recorder(behaviour)
        summary = self.run_plan(["가", "나", "다"], rec)
        self.assertEqual(len(rec.urls), 3)
        self.assertEqual((summary["ok"], summary["error"]), (2, 1))
        self.assertIsNone(summary["blocked_at"])
        self.assertAlmostEqual(summary["fail_ratio"], 1 / 3)

    def test_실패한_건은_다시_돌리면_다시_받는다(self):
        """실패는 캐시가 아니다 — 같은 --out 으로 재실행하면 그것만 받는다."""
        def once(url, n):
            raise HTTPError(url, 503, "nope", {}, None)

        self.run_plan(["가"], Recorder(once))
        rec = Recorder()
        summary = self.run_plan(["가"], rec)
        self.assertEqual((summary["ok"], summary["cached"]), (1, 0))

    def test_100건_응답을_센다(self):
        """상한에 닿은 요청 수는 창이 너무 넓은지 보는 눈금이다."""
        body = FEED.replace(b"</channel>", b"<item><title>x</title></item>" * 120 + b"</channel>")
        rec = Recorder(lambda url, n: (body, 200, url))
        summary = self.run_plan(["가"], rec)
        self.assertEqual(summary["saturated"], 1)

    def test_summary_json_을_남긴다(self):
        self.run_plan(["가"], Recorder())
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["plan"], 1)
        self.assertIn("finished_at", summary)


if __name__ == "__main__":
    unittest.main()
