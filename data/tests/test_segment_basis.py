"""부문 합계를 **연결·별도 둘 다와 대조**하는지 본다.

부문표가 어느 기준인지는 표마다 다르다. 기아 2022 표 68 은 별도 기준이라 명세 행
합이 별도 매출과 1원까지 같은데, 연결 매출(86.56조)과만 대조하던 때는 46% 차이로
버려졌다. 가까운 쪽으로 판정하되 **어느 쪽에 맞췄는지를 남긴다** — 말없이
바꿔치기하면 나중에 값을 못 믿는다.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA))

from pipeline.business_report import segments as S  # noqa: E402
from pipeline.business_report.doc import Document  # noqa: E402
from pipeline.patterns import patterns  # noqa: E402

P = patterns()

XML = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT><BODY>
<TITLE>1. 사업의 개요</TITLE>
<P>(단위: 백만원)</P>
<TABLE>
  <TR><TD>사업부문</TD><TD>매출액</TD></TR>
  <TR><TD>반도체</TD><TD>6,000</TD></TR>
  <TR><TD>디스플레이</TD><TD>4,000</TD></TR>
</TABLE>
</BODY></DOCUMENT>
"""

CONSOLIDATED = 25_000_000_000.0     # 연결 250억 — 표(100억)와 안 맞는다
SEPARATE = 10_000_000_000.0         # 별도 100억 — 표와 정확히 맞는다


class BasisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "document_00000000000000.xml"
        path.write_text(XML, encoding="utf-8")
        cls.doc = Document(path, P, rcept_no="00000000000000")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_표가_별도_기준이면_별도와_맞춘다(self):
        r = S.extract(self.doc, CONSOLIDATED, P, alt_revenues={"separate": SEPARATE})
        self.assertEqual(r.verdict, S.VERIFIED)
        self.assertEqual(r.revenue_basis, "separate")
        self.assertEqual(r.external_revenue, SEPARATE)
        self.assertEqual(r.gap_ratio, 0.0)

    def test_기존_기준이_맞으면_그대로_쓴다(self):
        r = S.extract(self.doc, SEPARATE, P, alt_revenues={"separate": SEPARATE})
        self.assertEqual(r.verdict, S.VERIFIED)
        self.assertEqual(r.revenue_basis, S.DEFAULT_BASIS)

    def test_둘_다_안_맞으면_가까운_쪽의_차이를_남긴다(self):
        """실패해도 어느 쪽에 얼마나 못 미쳤는지 보여야 패턴을 늘릴 수 있다."""
        r = S.extract(self.doc, CONSOLIDATED, P, alt_revenues={"separate": 12_000_000_000.0})
        self.assertEqual(r.verdict, S.MISMATCH)
        self.assertEqual(r.revenue_basis, "separate")
        self.assertAlmostEqual(r.gap_ratio, 0.1667, places=3)

    def test_대조할_값이_없으면_예전처럼_no_external(self):
        r = S.extract(self.doc, None, P, alt_revenues=None)
        self.assertEqual(r.verdict, S.NO_EXTERNAL)

    def test_빈_값은_후보에서_뺀다(self):
        """0 이나 None 을 후보로 넣으면 0 나누기가 된다."""
        r = S.extract(self.doc, SEPARATE, P, alt_revenues={"separate": 0.0, "other": None})
        self.assertEqual(r.verdict, S.VERIFIED)
        self.assertEqual(r.revenue_basis, S.DEFAULT_BASIS)

    def test_별도만_있고_기존_값이_없어도_맞춘다(self):
        r = S.extract(self.doc, None, P, alt_revenues={"separate": SEPARATE})
        self.assertEqual(r.verdict, S.VERIFIED)
        self.assertEqual(r.revenue_basis, "separate")


if __name__ == "__main__":
    unittest.main()
