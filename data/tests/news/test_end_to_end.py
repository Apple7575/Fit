"""raw → manifest → staged → curated → 검증까지 한 번에 돌린다.

실제 뉴스 데이터가 없는 동안 검증 1~13 번이 "데이터가 있으면 실제로 통과하는가" 를
확인할 방법이 이것뿐이다. 입력은 손으로 만든 최소 RSS 이며(tests/news/fixtures.py)
`data/raw/` 나 `data/staged/` 에 남기지 않는다 — 전부 임시 폴더에서 돌고 지워진다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.news import corpmap, curate, manifest, rawstore, stage, verify
from pipeline.news.schema import PROVIDER, SEED_TABLE
from tests.news import fixtures

TARGET_START, TARGET_END = "2026-09-06", "2026-09-07"
IN_WINDOW = "Sat, 05 Sep 2026 23:30:00 GMT"
OUT_WINDOW = "Sat, 05 Sep 2026 10:00:00 GMT"
RUN_ID = "20260906T001000Z-abcdef01"


class EndToEndTest(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.raw = root / "raw" / PROVIDER / "articles"
        self.staged = root / "staged" / PROVIDER
        self.seed = root / "curated" / "seed"
        self.manifests = root / "manifests" / PROVIDER
        for patch in (
            mock.patch.object(rawstore, "RAW_DIR", self.raw),
            mock.patch.object(manifest, "MANIFEST_DIR", self.manifests),
            mock.patch.object(stage, "STAGED_DIR", self.staged),
            mock.patch.object(verify, "STAGED_DIR", self.staged),
            mock.patch.object(verify, "SEED_DIR", self.seed),
            mock.patch.object(curate, "SEED_DIR", self.seed),
            mock.patch.object(curate, "SEED_MANIFEST_DIR", root / "manifests" / "seed"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

        plan = fixtures.daily_plan(TARGET_START, TARGET_END)
        items = [
            fixtures.item("삼성전자 테일러 공장 가동", "https://n1.test/a1", "g1", IN_WINDOW),
            fixtures.item("삼성전자 3분기 실적", "https://n2.test/a2?utm_source=x", "g2", IN_WINDOW),
            # 같은 기사가 두 번 관측된 경우
            fixtures.item("삼성전자 테일러 공장 가동", "https://n1.test/a1", "g1", IN_WINDOW),
            # 기간 밖
            fixtures.item("어제 기사", "https://n3.test/a3", "g3", OUT_WINDOW),
            # 입력 결함
            fixtures.item("", "https://n4.test/a4", "g4", IN_WINDOW),
            # Google 경유 링크만 있는 경우 — original_url 은 NULL 이 된다
            fixtures.item("링크 미확보 기사", "https://news.google.com/rss/articles/xyz", "g5", IN_WINDOW),
        ]
        fixtures.write_run(
            self.raw / RUN_ID,
            [("day0", fixtures.feed([]), plan[0][0], plan[0][1]),
             ("day1", fixtures.feed(items), plan[1][0], plan[1][1])],
        )
        self.mapper = corpmap.load()

    def _pipeline(self):
        run = rawstore.load_run(RUN_ID)
        manifest.write(manifest.build(run, TARGET_START, TARGET_END))
        result = stage.stage_run(run, self.mapper, TARGET_START, TARGET_END)
        stage.write(result)
        curated = curate.build(curate.load_staged(self.staged))
        curate.write(curated)
        return result, curated

    def test_전체_흐름과_검증_1_13(self):
        result, curated = self._pipeline()

        # 관측 6건 = 대표 3 + 중복 1 + 제외 2
        self.assertEqual(result.summary["raw_observations"], 6)
        self.assertEqual(result.summary["staged_rows"], 3)
        self.assertEqual(result.summary["duplicate_rows"], 1)
        self.assertEqual(result.summary["rejected_rows"], 2)
        self.assertEqual(result.summary["corp_map_reasons"], {})

        # 시드는 URL 이 있는 2건 + Google 링크뿐인 1건 = 3건
        self.assertEqual(curated.summary["seed_rows"], 3)
        self.assertEqual(curated.summary["original_url_null_rows"], 1)
        self.assertEqual(curated.summary["distinct_corp_codes"], 1)
        self.assertTrue((self.seed / f"{SEED_TABLE}.csv").exists())

        checks = {c.number: c for c in (
            verify.check_01_raw_vs_manifest(), verify.check_02_record_counts(),
            verify.check_03_exclusions(), verify.check_04_article_key_unique(),
            verify.check_05_url_duplicates(), verify.check_06_corp_mapping(),
            verify.check_07_published_at(), verify.check_08_required_nulls(),
            verify.check_09_headers(), verify.check_10_seed_keys(),
            verify.check_11_foreign_keys(), verify.check_13_determinism(),
        )}
        for number, check in sorted(checks.items()):
            self.assertEqual(check.status, "pass",
                             f"{number}번 {check.name}: {check.detail}")

        # 집계가 숫자로 남는지 — 이 값들이 최종 보고의 근거다
        self.assertEqual(checks[3].detail["reject_reasons"],
                         {"input_defect:missing_title": 1, "outside_target_window": 1})
        self.assertEqual(checks[6].detail["mapped"], 3)
        self.assertEqual(checks[6].detail["unmapped"], 0)
        self.assertEqual(checks[7].detail["parsed"], 6)
        self.assertEqual(checks[7].detail["unparsed"], 0)

    def test_manifest_가_원본을_그대로_센다(self):
        self._pipeline()
        document = manifest.load_all(self.manifests)[0]
        self.assertEqual(document["provider"], PROVIDER)
        self.assertEqual(document["collection_run_id"], RUN_ID)
        self.assertTrue(document["collection_run_id_conforms"])
        self.assertEqual(document["record_count"], 6)
        self.assertEqual(document["unique_article_keys"], 5)
        self.assertEqual(document["duplicate_candidate_count"], 1)
        self.assertEqual(document["success_count"], 2)
        self.assertEqual(document["fail_count"], 0)
        self.assertEqual(document["raw_file_count"], 2)
        self.assertFalse(document["full_coverage_verified"])
        self.assertTrue(all(f["sha256"] for f in document["raw_files"]))

    def test_원본은_고치지_않는다(self):
        before = {p.name: p.read_bytes() for p in (self.raw / RUN_ID).glob("*.xml")}
        self._pipeline()
        after = {p.name: p.read_bytes() for p in (self.raw / RUN_ID).glob("*.xml")}
        self.assertEqual(before, after)

    def test_매핑_실패가_섞이면_시드에서_빠진다(self):
        # 검색어를 기업 마스터에 없는 이름으로 바꿔 다시 정제한다.
        plan = fixtures.daily_plan(TARGET_START, TARGET_END)
        fixtures.write_run(
            self.raw / "20260906T001000Z-abcdef02",
            [("day0", fixtures.feed([]), plan[0][0], plan[0][1]),
             ("day1", fixtures.feed([
                 fixtures.item("어떤 기사", "https://n9.test/a9", "g9", IN_WINDOW)]),
              plan[1][0], plan[1][1])],
            company="존재하지않는회사",
        )
        for run_id in rawstore.list_runs():
            run = rawstore.load_run(run_id)
            manifest.write(manifest.build(run, TARGET_START, TARGET_END))
            stage.write(stage.stage_run(run, self.mapper, TARGET_START, TARGET_END))
        curated = curate.build(curate.load_staged(self.staged))
        curate.write(curated)
        self.assertEqual(curated.summary["seed_rows"], 3)
        # 중복은 duplicates.csv 로 갈라져 있어 시드 입력(articles.csv)에 애초에 없다.
        self.assertEqual(curated.summary["drop_reasons"],
                         {"corp_code_unresolved:not_in_company_universe": 1})
        mapping = verify.check_06_corp_mapping()
        self.assertEqual(mapping.status, "pass")
        self.assertEqual(mapping.detail["unmapped"], 1)
        self.assertEqual(mapping.detail["reasons"], {"not_in_company_universe": 1})
        # FK 검사는 시드에 들어간 것만 본다 — 매핑 실패는 애초에 시드에 없다
        self.assertEqual(verify.check_11_foreign_keys().status, "pass")


if __name__ == "__main__":
    unittest.main()
