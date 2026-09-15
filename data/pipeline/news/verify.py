"""뉴스 데이터 검증. 실패를 숨기지 않고, 데이터를 보정하지 않는다.

기준 문서 11장의 14개 항목을 그대로 구현한다. 원본이 없으면 해당 항목은 `skip` 이고,
`skip` 을 `pass` 로 세지 않는다 — 데이터 없이 통과했다고 보고하는 것이 가장 나쁘다.

돌리는 방법은 `data/scripts/verify_news.py` 를 보라.
"""
from __future__ import annotations

import filecmp
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.news import corpmap, curate, flyway, manifest, rawstore, stage
from pipeline.news.csvio import read_csv, row_count
from pipeline.news.schema import PROVIDER, SEED_FIELDS, SEED_TABLE

DATA = rawstore.ROOT
DOCS = DATA / "docs"
STAGED_DIR = DATA / "staged" / PROVIDER
SEED_DIR = DATA / "curated" / "seed"


@dataclass
class Check:
    number: int
    name: str
    status: str                  # pass / fail / skip
    detail: dict = field(default_factory=dict)

    @property
    def line(self) -> str:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[self.status]
        return f"[{self.number:2d}] {mark}  {self.name}"


def _staged_runs() -> list[Path]:
    return sorted(p.parent for p in STAGED_DIR.glob("*/articles.csv"))


def _staged_rows() -> list[dict]:
    return curate.load_staged(STAGED_DIR)


def check_01_raw_vs_manifest() -> Check:
    """원본 파일 수와 manifest 가 기록한 파일 수를 대조한다."""
    runs = rawstore.list_runs()
    if not runs:
        return Check(1, "원본 파일 수 ↔ manifest 파일 수", "skip",
                     {"reason": "raw/google_news_rss/articles 에 수집 실행이 없다"})
    problems, rows = [], []
    for run_id in runs:
        run = rawstore.load_run(run_id)
        path = manifest.path_for(run_id)
        if not path.exists():
            problems.append(f"{run_id}: manifest 없음")
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        actual = {f.path.name for f in run.files}
        recorded = {Path(f["path"]).name for f in document.get("raw_files", [])}
        rows.append({"run_id": run_id, "raw_files": len(actual), "manifest_files": len(recorded)})
        if actual != recorded:
            problems.append(f"{run_id}: 원본만 {sorted(actual - recorded)} / manifest 만 {sorted(recorded - actual)}")
        for raw in run.files:
            if raw.checksum_matches is False:
                problems.append(f"{run_id}: {raw.path.name} 체크섬 불일치")
    return Check(1, "원본 파일 수 ↔ manifest 파일 수", "fail" if problems else "pass",
                 {"runs": rows, "problems": problems})


def check_02_record_counts() -> Check:
    """원본 레코드 수가 staged 결과에 전부 반영됐는지 본다."""
    runs = _staged_runs()
    if not runs:
        return Check(2, "원본 레코드 수 ↔ staged 처리 결과", "skip", {"reason": "staged 산출물이 없다"})
    problems, rows = [], []
    for directory in runs:
        summary = json.loads((directory / "stage_summary.json").read_text(encoding="utf-8"))
        parts = summary["staged_rows"] + summary["duplicate_rows"] + summary["rejected_rows"]
        rows.append({"run_id": summary["collection_run_id"], "raw_observations": summary["raw_observations"],
                     "staged+duplicate+rejected": parts,
                     "in_window": summary["in_window_observations"],
                     "collector_target_observations": summary["collector_target_observations"]})
        if parts != summary["raw_observations"]:
            problems.append(f"{summary['collection_run_id']}: 원본 {summary['raw_observations']} ≠ 처리 합 {parts}")
        expected = summary["collector_target_observations"]
        if expected is not None and expected != summary["in_window_observations"]:
            problems.append(f"{summary['collection_run_id']}: 수집기 기간내 {expected} ≠ 정제 기간내 {summary['in_window_observations']}")
    return Check(2, "원본 레코드 수 ↔ staged 처리 결과", "fail" if problems else "pass",
                 {"runs": rows, "problems": problems})


def check_03_exclusions() -> Check:
    """제외된 레코드와 사유를 집계한다. 집계 자체가 목적이므로 실패 조건은 사유 누락뿐이다."""
    runs = _staged_runs()
    if not runs:
        return Check(3, "제외 레코드·사유 집계", "skip", {"reason": "staged 산출물이 없다"})
    reasons: dict[str, int] = {}
    missing = 0
    for directory in runs:
        for row in read_csv(directory / "rejects.csv"):
            reason = row.get("reject_reason") or ""
            if not reason:
                missing += 1
            reasons[reason or "(사유 없음)"] = reasons.get(reason or "(사유 없음)", 0) + 1
    return Check(3, "제외 레코드·사유 집계", "fail" if missing else "pass",
                 {"reject_reasons": dict(sorted(reasons.items())), "rows_without_reason": missing})


def check_04_article_key_unique() -> Check:
    rows = _staged_rows()
    if not rows:
        return Check(4, "기사 식별자 중복", "skip", {"reason": "staged 산출물이 없다"})
    seen: dict[str, int] = {}
    for row in rows:
        seen[row["article_key"]] = seen.get(row["article_key"], 0) + 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    return Check(4, "기사 식별자 중복", "fail" if duplicates else "pass",
                 {"rows": len(rows), "distinct": len(seen), "duplicate_keys": duplicates})


def check_05_url_duplicates() -> Check:
    rows = _staged_rows()
    if not rows:
        return Check(5, "URL 중복", "skip", {"reason": "staged 산출물이 없다"})
    seen: dict[str, list[str]] = {}
    for row in rows:
        norm = row.get("original_url_norm") or ""
        if norm:
            seen.setdefault(norm, []).append(row["article_key"])
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    return Check(5, "URL 중복", "fail" if duplicates else "pass",
                 {"rows_with_original_url": sum(1 for v in seen.values() for _ in v),
                  "distinct_normalized_urls": len(seen),
                  "duplicate_urls": {k: v for k, v in list(duplicates.items())[:20]},
                  "duplicate_url_count": len(duplicates)})


def check_06_corp_mapping() -> Check:
    """매핑 성공·실패 건수. 실패가 있는 것 자체는 실패가 아니다 — 사유가 없으면 실패다."""
    rows = _staged_rows()
    if not rows:
        return Check(6, "corp_code 매핑 성공·실패", "skip", {"reason": "staged 산출물이 없다"})
    mapped = [r for r in rows if r.get("corp_code")]
    unmapped = [r for r in rows if not r.get("corp_code")]
    without_reason = [r["article_key"] for r in unmapped if not r.get("corp_map_reason")]
    methods: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in mapped:
        methods[row.get("corp_map_method") or "(none)"] = methods.get(row.get("corp_map_method") or "(none)", 0) + 1
    for row in unmapped:
        reasons[row.get("corp_map_reason") or "(none)"] = reasons.get(row.get("corp_map_reason") or "(none)", 0) + 1
    return Check(6, "corp_code 매핑 성공·실패", "fail" if without_reason else "pass",
                 {"mapped": len(mapped), "unmapped": len(unmapped), "methods": methods,
                  "reasons": reasons, "unmapped_without_reason": without_reason[:20]})


def check_07_published_at() -> Check:
    runs = _staged_runs()
    if not runs:
        return Check(7, "published_at 파싱 성공·실패", "skip", {"reason": "staged 산출물이 없다"})
    parsed = unparsed = 0
    for directory in runs:
        summary = json.loads((directory / "stage_summary.json").read_text(encoding="utf-8"))
        parsed += summary["published_at_parsed"]
        unparsed += summary["published_at_unparsed"]
    return Check(7, "published_at 파싱 성공·실패", "pass",
                 {"parsed": parsed, "unparsed": unparsed,
                  "note": "실패 행은 rejects.csv 의 unparsed_published_at 으로 분리된다"})


def check_08_required_nulls() -> Check:
    """staged 필수 컬럼과 시드의 NOT NULL 컬럼에 빈 값이 없는지 본다."""
    schema = flyway.load()
    table = schema.table(SEED_TABLE)
    required_seed = [c.name for c in table.ordered()
                     if not c.nullable and not c.identity and not c.default]
    problems: dict[str, int] = {}
    rows = _staged_rows()
    for column in ("article_key", "title", "provider", "collection_run_id", "source_raw_file"):
        empty = sum(1 for r in rows if not (r.get(column) or ""))
        if empty:
            problems[f"staged.{column}"] = empty
    seed_path = SEED_DIR / f"{SEED_TABLE}.csv"
    seed_rows = read_csv(seed_path) if seed_path.exists() else []
    for column in required_seed:
        empty = sum(1 for r in seed_rows if not (r.get(column) or ""))
        if empty:
            problems[f"{SEED_TABLE}.{column}"] = empty
    if not rows and not seed_rows:
        return Check(8, "필수 컬럼 null", "skip", {"reason": "staged·curated 산출물이 없다"})
    return Check(8, "필수 컬럼 null", "fail" if problems else "pass",
                 {"staged_rows": len(rows), "seed_rows": len(seed_rows),
                  "seed_not_null_columns": required_seed, "violations": problems})


def check_09_headers() -> Check:
    """curated 헤더·데이터 사전을 Flyway 스키마와 대조한다."""
    schema = flyway.load()
    problems = []
    expected = curate.seed_header(schema)
    if expected != SEED_FIELDS:
        problems.append(f"SEED_FIELDS 가 Flyway 와 다르다: {SEED_FIELDS} != {expected}")
    seed_path = SEED_DIR / f"{SEED_TABLE}.csv"
    if seed_path.exists():
        from pipeline.news.csvio import header as read_header
        actual = read_header(seed_path)
        if actual != expected:
            problems.append(f"{seed_path.name} 헤더가 다르다: {actual} != {expected}")

    # 데이터 사전이 스키마와 벌어졌는지 본다. 사전은 손으로 쓰므로 이 대조가 유일한 방어다.
    fields_path = DOCS / "data_fields.csv"
    dictionary_detail = {}
    if fields_path.exists():
        documented = {(r["table_name"], r["column_name"]) for r in read_csv(fields_path)}
        actual_columns = {
            (t.qualified, c.name) for t in schema.tables.values() for c in t.ordered()
        }
        missing = sorted(actual_columns - documented)
        extra = sorted(documented - actual_columns)
        dictionary_detail = {"documented": len(documented), "schema": len(actual_columns),
                             "missing_from_dictionary": missing, "not_in_schema": extra}
        if missing or extra:
            problems.append(f"data_fields.csv 불일치 — 누락 {len(missing)}건, 스키마에 없음 {len(extra)}건")
    else:
        problems.append("data_fields.csv 가 없다")
    return Check(9, "curated 헤더·데이터 사전 ↔ Flyway 컬럼", "fail" if problems else "pass",
                 {"seed_header": expected, "seed_csv_exists": seed_path.exists(),
                  "data_fields": dictionary_detail, "problems": problems})


def check_10_seed_keys() -> Check:
    """시드의 PK·UNIQUE 중복. (corp_code, original_url) 을 부분 UNIQUE 로 본다.

    V12 의 company_news_url_uk 가 그 규칙이었고 V13 이 news_article 로 옮기면서
    인덱스를 다시 만들지 않았다. 복원 요청과 별개로 이 검사는 유지한다 —
    시드가 중복을 담지 않는다는 사실 자체는 계속 확인해야 한다.
    """
    seed_path = SEED_DIR / f"{SEED_TABLE}.csv"
    if not seed_path.exists():
        return Check(10, "시드 PK·UNIQUE 중복", "skip", {"reason": f"{seed_path.name} 이 없다"})
    rows = read_csv(seed_path)
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        url = row.get("original_url") or ""
        if url:
            key = (row["corp_code"], url)
            seen[key] = seen.get(key, 0) + 1
    duplicates = {f"{k[0]}|{k[1]}": v for k, v in seen.items() if v > 1}
    return Check(10, "시드 PK·UNIQUE 중복", "fail" if duplicates else "pass",
                 {"rows": len(rows), "keyed_rows": len(seen), "duplicates": duplicates,
                  "note": "id 는 identity 라 CSV 에 없다. 중복 검사 대상은 부분 UNIQUE 인덱스뿐"})


def check_11_foreign_keys() -> Check:
    """corp_code 가 company 마스터의 원천에 있는지 본다.

    대조 상대는 `curated/seed/company.csv` 다. 예전에는 `company_universe.csv`
    (3,930건)를 봤는데, company 시드가 정규 시장 2,703건만 담게 되면서 그쪽이
    실제보다 느슨해졌다 — corp_cls=E 기업을 가리키는 행이 통과하고 적재에서
    FK 로 터진다.
    """
    seed_path = SEED_DIR / f"{SEED_TABLE}.csv"
    if not seed_path.exists():
        return Check(11, "FK 참조 무결성", "skip", {"reason": f"{seed_path.name} 이 없다"})
    company_seed = SEED_DIR / "company.csv"
    source = (company_seed if company_seed.exists()
              else corpmap.CONFIG / "company_universe.csv")
    master = {(r.get("corp_code") or "").strip() for r in read_csv(source)}
    rows = read_csv(seed_path)
    missing = sorted({r["corp_code"] for r in rows if r["corp_code"] not in master})
    return Check(11, "FK 참조 무결성", "fail" if missing else "pass",
                 {"rows": len(rows), "master_source": source.name,
                  "master_rows": len(master),
                  "corp_codes_not_in_master": missing[:20], "missing_count": len(missing),
                  "note": "company 테이블은 curated/seed/company.csv 로 적재된다 "
                          "(scripts/load_company.py)"})


def check_12_inventory_row_counts() -> Check:
    """seed_csv_inventory.csv 의 row_count 가 실제 CSV 행 수와 같은지 본다."""
    path = DOCS / "seed_csv_inventory.csv"
    if not path.exists():
        return Check(12, "seed_csv_inventory.csv row_count ↔ 실제 행 수", "fail",
                     {"problems": ["seed_csv_inventory.csv 가 없다"]})
    entries = read_csv(path)
    problems, rows = [], []
    for row in entries:
        csv_path = (row.get("seed_csv_path") or "").strip()
        recorded = (row.get("row_count") or "").strip()
        if not csv_path or csv_path == "-":
            continue
        target = DATA.parent / csv_path
        if not target.exists():
            # Git 추적 대상이 아닌 산출물은 다른 사람 PC 에 없는 것이 정상이다.
            status = "not_present_locally" if row.get("tracked_by_git") == "no" else "missing"
            if status == "missing":
                problems.append(f"{row['table_name']}: 추적 대상인데 파일이 없다 ({csv_path})")
            rows.append({"table": row["table_name"], "path": csv_path, "state": status,
                         "recorded": recorded})
            continue
        actual = row_count(target)
        rows.append({"table": row["table_name"], "path": csv_path, "state": "present",
                     "recorded": recorded, "actual": actual})
        if recorded != str(actual):
            problems.append(f"{row['table_name']}: row_count={recorded} ≠ 실제 {actual} ({csv_path})")

    # 목록에 빠진 테이블이 없는지도 본다. 빠지면 "시드 없음" 이 아니라 "모른다" 가 된다.
    listed = {r["table_name"] for r in entries}
    schema_tables = {t.qualified for t in flyway.load().tables.values()}
    unlisted = sorted(schema_tables - listed)
    if unlisted:
        problems.append(f"목록에 없는 테이블 {len(unlisted)}개: {', '.join(unlisted)}")
    return Check(12, "seed_csv_inventory.csv row_count ↔ 실제 행 수", "fail" if problems else "pass",
                 {"entries": rows, "tables_listed": len(schema_tables & listed),
                  "tables_in_schema": len(schema_tables), "unlisted_tables": unlisted,
                  "problems": problems})


def _seed_build_options() -> dict:
    """시드를 만들 때 쓴 선택을 manifest 에서 읽는다.

    `curate.build` 의 기본값이 아닌 선택(예: `--per-company 5`)으로 만든 시드를
    기본값으로 다시 만들면 당연히 달라진다. 그것은 결정성 문제가 아니라 **다른
    명령을 돌린 것**이라, 재실행 대조는 같은 선택으로 해야 뜻이 있다.
    manifest 가 없거나 키가 없으면 기본값으로 둔다.
    """
    path = curate.SEED_MANIFEST_DIR / f"{SEED_TABLE}.json"
    if not path.exists():
        return {}
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    options: dict = {}
    if saved.get("per_company_limit"):
        options["per_company"] = int(saved["per_company_limit"])
    if saved.get("source_column_maps_to"):
        options["source_column"] = saved["source_column_maps_to"]
    return options


def check_13_determinism() -> Check:
    """같은 원본으로 다시 정제·시드 생성해 바이트가 같은지 본다."""
    runs = rawstore.list_runs()
    if not runs:
        return Check(13, "재실행 결정성", "skip", {"reason": "원본이 없어 재실행할 수 없다"})
    mapper = corpmap.load()
    problems, compared = [], []
    with tempfile.TemporaryDirectory() as temporary:
        scratch = Path(temporary)
        for run_id in runs:
            existing = STAGED_DIR / run_id / "articles.csv"
            if not existing.exists():
                problems.append(f"{run_id}: staged articles.csv 가 없어 대조할 수 없다")
                continue
            result = stage.stage_run(rawstore.load_run(run_id), mapper)
            again = scratch / run_id
            stage.write(result, again)
            same = filecmp.cmp(existing, again / "articles.csv", shallow=False)
            compared.append({"run_id": run_id, "articles_csv_identical": same})
            if not same:
                problems.append(f"{run_id}: articles.csv 가 재실행 결과와 다르다")
        seed_path = SEED_DIR / f"{SEED_TABLE}.csv"
        if seed_path.exists():
            # 시드를 만들 때 준 선택(기업별 상한·source 컬럼)을 manifest 에서 읽어
            # 그대로 다시 준다. 기본값으로 다시 만들면 "재실행하면 달라진다"가
            # 아니라 "다른 명령을 돌렸다"를 잡게 된다.
            options = _seed_build_options()
            rebuilt = curate.build(_staged_rows(), **options)
            copy = scratch / "seed"
            copy.mkdir(parents=True, exist_ok=True)
            from pipeline.news.csvio import write_csv
            write_csv(copy / f"{SEED_TABLE}.csv", SEED_FIELDS, rebuilt.rows)
            same = filecmp.cmp(seed_path, copy / f"{SEED_TABLE}.csv", shallow=False)
            compared.append({"seed": SEED_TABLE, "identical": same})
            if not same:
                problems.append(f"{SEED_TABLE}.csv 가 재생성 결과와 다르다")
        shutil.rmtree(scratch, ignore_errors=True)
    return Check(13, "재실행 결정성", "fail" if problems else "pass",
                 {"compared": compared, "problems": problems})


def check_14_unit_tests() -> Check:
    """정제·시드 코드의 단위 테스트를 돌린다."""
    import subprocess
    import sys

    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/news", "-t", "."],
        cwd=DATA, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (process.stderr or process.stdout or "").strip().splitlines()[-6:]
    return Check(14, "단위 테스트", "pass" if process.returncode == 0 else "fail",
                 {"returncode": process.returncode, "output_tail": tail})


ALL_CHECKS = (
    check_01_raw_vs_manifest, check_02_record_counts, check_03_exclusions,
    check_04_article_key_unique, check_05_url_duplicates, check_06_corp_mapping,
    check_07_published_at, check_08_required_nulls, check_09_headers,
    check_10_seed_keys, check_11_foreign_keys, check_12_inventory_row_counts,
    check_13_determinism, check_14_unit_tests,
)


def run_all() -> list[Check]:
    checks = []
    for function in ALL_CHECKS:
        try:
            checks.append(function())
        except Exception as error:                       # noqa: BLE001 — 검증기가 죽으면 안 된다
            number = int(function.__name__.split("_")[1])
            checks.append(Check(number, function.__name__, "fail",
                                {"exception": f"{type(error).__name__}: {error}"}))
    return checks
